"""Servidor do simulador: interface em /simulador e a ponte câmera sintética → GSA.

A ponte faz o papel do sistema de detecção externo (o mesmo de `deteccao/contador_yolo.py`):

1. recebe do navegador os quadros com as detecções sintéticas (caixas, classes, ids e confiança);
2. conta veículos distintos por zona e janela com `deteccao.zonas.ContadorJanela`;
3. ao fim de cada janela (`intervaloContagem` do GSA, em tempo simulado) monta o lote com
   `deteccao.zonas.montar_lote` e o envia para `POST /cruzamentos/{id}/leituras` com a chave do
   sistema de detecção, que nunca sai do servidor;
4. devolve ao navegador o `cicloGerado` e o plano de execução montado a partir dele.

Somente para demonstração: qualquer pessoa que alcance estas rotas consegue enviar leituras ao
cruzamento simulado. Por isso o simulador fica desligado por padrão e `python -m simulador`
usa um banco de demonstração próprio.
"""

import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, FastAPI, Request, Response, status
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.exceptions import ErroDominio, RegraDeNegocioViolada
from deteccao.zonas import CLASSES_PADRAO, configuracao_de_dicionario, montar_lote
from simulador import planos
from simulador.cliente_gsa import URL_INTERNA, ClienteGSA, ErroGSA
from simulador.demanda import PASSO_MINUTOS, perfil_por_via
from simulador.esquemas import PlanoFixoPedido, QuadrosEnviar, SessaoCriar
from simulador.sessoes import RepositorioSessoes, Sessao, SessaoInexistente, SessaoSubstituida

PASTA_WEB = Path(__file__).parent / "web"
CONFIANCA_MINIMA = 0.3  # a mesma confiança mínima padrão do contador YOLO (--confianca)
CAMPOS_PARAMETROS = (
    "duracaoCiclo",
    "intervaloContagem",
    "tempoMaximoSemLeitura",
    "fluxoSaturacaoPorFaixa",
    "cicloMinimo",
    "cicloMaximo",
    "limiteFluxoBaixo",
    "limiteFluxoModerado",
    "limiteFluxoAlto",
)


class GSAIndisponivel(ErroDominio):
    status_code = 503
    titulo = "GSA indisponível"


class NaoEncontrado(ErroDominio):
    status_code = 404
    titulo = "Recurso não encontrado"


class SessaoEncerrada(ErroDominio):
    status_code = 409
    titulo = "Sessão substituída"


@dataclass
class ContextoSimulador:
    cliente: ClienteGSA
    sessoes: RepositorioSessoes
    url_painel: str


def _contexto(request: Request) -> ContextoSimulador:
    return request.app.state.simulador


Contexto = Annotated[ContextoSimulador, Depends(_contexto)]
router = APIRouter(prefix="/simulador/api", include_in_schema=False)


async def _obter(cliente: ClienteGSA, caminho: str, **parametros: Any) -> Any:
    try:
        return await cliente.obter(caminho, **parametros)
    except ErroGSA as erro:
        if erro.status == 404:
            raise NaoEncontrado(erro.mensagem) from erro
        raise GSAIndisponivel(erro.mensagem) from erro


async def _carregar(cliente: ClienteGSA, cruzamento_id: int) -> tuple[dict, dict]:
    cruzamento = await _obter(cliente, f"/cruzamentos/{cruzamento_id}")
    parametros = await _obter(cliente, "/parametros")
    return cruzamento, parametros


def _vias_suportadas(cruzamento: dict) -> int:
    return sum(
        1
        for via in cruzamento["vias"]
        if via["direcao"] in planos.EIXO_DA_DIRECAO and planos.semaforo_ativo(via)
    )


@router.get("/estado")
async def estado(ctx: Contexto) -> dict:
    """Situação do simulador e da conexão com o GSA, e o cruzamento sugerido para abrir."""
    settings = get_settings()
    resposta: dict[str, Any] = {
        "habilitado": True,
        "modoApi": "remoto" if ctx.cliente.remoto else "local",
        "apiUrl": ctx.cliente.base_url if ctx.cliente.remoto else None,
        "chaveConfigurada": bool(ctx.cliente.chave),
        "urlPainel": ctx.url_painel,
        "versao": settings.versao,
        "gsaOnline": False,
        "cruzamentos": [],
        "cruzamentoPadrao": None,
        "erro": None,
    }
    try:
        cruzamentos = await ctx.cliente.obter("/cruzamentos")
        resposta["gsaOnline"] = True
        resposta["cruzamentos"] = [
            {"id": c["id"], "nome": c["nome"], "status": c["status"]} for c in cruzamentos
        ]
        # Sugere o cruzamento ativo com mais vias representáveis (o B do seed: 4 vias)
        melhor = None
        for item in [c for c in cruzamentos if c["status"] == "ativo"][:20]:
            detalhe = await ctx.cliente.obter(f"/cruzamentos/{item['id']}")
            pontos = _vias_suportadas(detalhe)
            if pontos and (melhor is None or pontos > melhor[0]):
                melhor = (pontos, item["id"])
        resposta["cruzamentoPadrao"] = melhor[1] if melhor else None
    except ErroGSA as erro:
        resposta["erro"] = erro.mensagem
    return resposta


@router.get("/cruzamentos/{cruzamento_id}/configuracao")
async def configuracao(cruzamento_id: int, ctx: Contexto) -> dict:
    """Vias, semáforos, estágios e parâmetros lidos da API do GSA, com o plano fixo inicial e
    o perfil de demanda de cada via."""
    cruzamento, parametros = await _carregar(ctx.cliente, cruzamento_id)
    vias = cruzamento["vias"]
    duracao = planos.duracao_do_ciclo(cruzamento, parametros)
    try:
        plano = planos.plano_fixo(vias, duracao, planos.faixas_de_fluxo(parametros))
    except planos.PlanoInvalido as erro:
        raise RegraDeNegocioViolada(f"Cruzamento {cruzamento_id}: {erro}") from erro
    perfil = perfil_por_via(vias)
    return {
        "cruzamento": {
            "id": cruzamento["id"],
            "nome": cruzamento["nome"],
            "status": cruzamento["status"],
            "regraTemporizacao": cruzamento["regraTemporizacao"],
            "duracaoCiclo": duracao,
            "duracaoCicloCadastrada": cruzamento["duracaoCiclo"],
        },
        "parametros": {campo: parametros[campo] for campo in CAMPOS_PARAMETROS},
        "janelaSegundos": parametros["intervaloContagem"],
        "vias": [
            {
                "id": via["id"],
                "nome": via["nome"],
                "direcao": via["direcao"],
                "quantidadeFaixas": via["quantidadeFaixas"],
                "estagio": via["estagio"],
                "semaforo": via["semaforo"],
                "ativa": planos.semaforo_ativo(via),
                "eixo": planos.EIXO_DA_DIRECAO.get(via["direcao"]),
            }
            for via in vias
        ],
        "planoFixo": plano,
        "perfilDemanda": {
            "passoMinutos": PASSO_MINUTOS,
            "vias": {str(via_id): valores for via_id, valores in perfil.items()},
        },
        "classes": list(CLASSES_PADRAO),
        "confiancaMinima": CONFIANCA_MINIMA,
        "avisos": planos.verificar_vias(vias),
        "urlPainel": f"{ctx.url_painel}?cruzamento={cruzamento_id}",
    }


@router.post("/cruzamentos/{cruzamento_id}/plano-fixo")
async def plano_fixo(cruzamento_id: int, dados: PlanoFixoPedido, ctx: Contexto) -> dict:
    """Plano de tempo fixo do cruzamento A da comparação, calculado pelo motor do GSA:
    `igual` é o plano fixo de segurança; `ajustado` usa a regra do cruzamento uma única vez,
    com a demanda média informada."""
    cruzamento, parametros = await _carregar(ctx.cliente, cruzamento_id)
    try:
        if dados.tipo == "ajustado":
            return planos.plano_ajustado(cruzamento, parametros, dados.taxas)
        return planos.plano_fixo(
            cruzamento["vias"],
            planos.duracao_do_ciclo(cruzamento, parametros),
            planos.faixas_de_fluxo(parametros),
        )
    except planos.PlanoInvalido as erro:
        raise RegraDeNegocioViolada(f"Cruzamento {cruzamento_id}: {erro}") from erro


@router.post("/sessoes", status_code=status.HTTP_201_CREATED)
async def criar_sessao(dados: SessaoCriar, ctx: Contexto) -> dict:
    """Cria a câmera sintética do cruzamento. A janela de contagem é o `intervaloContagem` do
    GSA; uma sessão nova do mesmo cruzamento substitui a anterior (uma câmera por cruzamento)."""
    cruzamento, parametros = await _carregar(ctx.cliente, dados.cruzamento_id)
    ids = {via["id"] for via in cruzamento["vias"]}
    alheias = sorted(z.via_id for z in dados.zonas if z.via_id not in ids)
    if alheias:
        raise RegraDeNegocioViolada(
            f"Vias {alheias} não pertencem ao cruzamento {dados.cruzamento_id}"
        )
    try:
        config = configuracao_de_dicionario(
            {
                "cruzamentoId": dados.cruzamento_id,
                "janelaSegundos": parametros["intervaloContagem"],
                "classes": list(CLASSES_PADRAO),
                "zonas": [
                    {"viaId": z.via_id, "nome": z.nome, "poligono": z.poligono} for z in dados.zonas
                ],
            }
        )
    except ValueError as erro:
        raise RegraDeNegocioViolada(f"Zonas de detecção inválidas: {erro}") from erro
    sessao = ctx.sessoes.criar(config, dados.confianca_minima)
    sessao.inicio_janela = dados.tempo_inicial
    sessao.ultimo_tempo = dados.tempo_inicial
    return {
        "sessaoId": sessao.id,
        "cruzamentoId": sessao.cruzamento_id,
        "tempoInicial": sessao.inicio_janela,
        "janelaSegundos": sessao.janela,
        "classes": list(config.classes),
        "confiancaMinima": sessao.confianca_minima,
        "zonas": len(config.zonas),
    }


def _sessao(ctx: ContextoSimulador, sessao_id: str) -> Sessao:
    try:
        return ctx.sessoes.obter(sessao_id)
    except SessaoInexistente as erro:
        raise NaoEncontrado("Sessão do simulador não existe ou expirou") from erro
    except SessaoSubstituida as erro:
        raise SessaoEncerrada(
            "Outra aba assumiu a câmera deste cruzamento; reinicie a simulação para retomar"
        ) from erro


@router.post("/sessoes/{sessao_id}/quadros")
async def receber_quadros(sessao_id: str, dados: QuadrosEnviar, ctx: Contexto) -> dict:
    """Recebe quadros da câmera sintética; a cada janela encerrada envia o lote ao GSA."""
    sessao = _sessao(ctx, sessao_id)
    sem_envio = set(dados.vias_sem_envio)
    envios = []
    async with sessao.trava:
        for quadro in sorted(dados.quadros, key=lambda q: q.t):
            if quadro.t <= sessao.ultimo_tempo:
                continue  # reenvio de quadros já contados
            sessao.registrar_quadro(quadro.deteccoes)
            sessao.ultimo_tempo = quadro.t
            if sessao.janela_terminou(quadro.t):
                envios.append(await _enviar_janela(ctx, sessao, quadro.t, sem_envio))
        parcial = sessao.contador.parcial()
    return {
        "tempoSimulado": max(sessao.ultimo_tempo, 0.0),
        "janela": {
            "inicio": sessao.inicio_janela,
            "duracao": sessao.janela,
            "parcial": {str(via_id): n for via_id, n in parcial.items()},
        },
        "envios": envios,
        "ultimoPlano": sessao.ultimo_plano,
    }


async def _enviar_janela(
    ctx: ContextoSimulador, sessao: Sessao, t: float, sem_envio: set[int]
) -> dict:
    inicio, fim, contagens = sessao.fechar_janela(t)
    enviadas = {via_id: n for via_id, n in contagens.items() if via_id not in sem_envio}
    envio: dict[str, Any] = {
        "janela": {"inicio": inicio, "fim": fim},
        "contagens": {str(via_id): n for via_id, n in contagens.items()},
        "viasOmitidas": sorted(set(contagens) & sem_envio),
        "lote": None,
        "status": None,
        "latenciaMs": None,
        "cicloGerado": None,
        "plano": None,
        "avisos": [],
        "erro": None,
    }
    if not enviadas:
        envio["erro"] = "Nenhuma via enviada: todas as câmeras estão em falha"
        return envio
    lote = montar_lote(sessao.cruzamento_id, enviadas)
    envio["lote"] = lote
    resposta = await ctx.cliente.enviar_leituras(sessao.cruzamento_id, lote)
    envio.update(status=resposta.status, latenciaMs=round(resposta.latencia_ms, 1))
    envio["erro"] = resposta.erro
    if not resposta.corpo:
        return envio
    envio["avisos"] = resposta.corpo.get("avisos", [])
    ciclo = resposta.corpo.get("cicloGerado")
    envio["cicloGerado"] = ciclo
    if ciclo is None:
        return envio
    try:
        # semáforos como estão agora, para o entreverde de cada estágio
        cruzamento = await ctx.cliente.obter(f"/cruzamentos/{sessao.cruzamento_id}")
        plano = planos.plano_do_ciclo(ciclo, cruzamento["vias"])
    except (ErroGSA, planos.PlanoInvalido) as erro:
        envio["erro"] = f"Ciclo recebido, mas o plano não pôde ser montado: {erro}"
        return envio
    sessao.sequencia_plano += 1
    plano["sequencia"] = sessao.sequencia_plano
    plano["janela"] = {"inicio": inicio, "fim": fim}
    sessao.ultimo_plano = plano
    envio["plano"] = plano
    return envio


@router.delete("/sessoes/{sessao_id}", status_code=status.HTTP_204_NO_CONTENT)
async def encerrar_sessao(sessao_id: str, ctx: Contexto) -> Response:
    ctx.sessoes.encerrar(sessao_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def montar_simulador(app: FastAPI, api_url: str | None = None) -> ContextoSimulador:
    """Acrescenta /simulador (interface) e /simulador/api (ponte) ao app do GSA."""
    existente = getattr(app.state, "simulador", None)
    if existente is not None:
        return existente
    # Alguns Windows registram .js como text/plain, e o navegador recusa módulos assim
    mimetypes.add_type("text/javascript", ".js")
    chave = get_settings().chave_api_deteccao
    if api_url:
        cliente = ClienteGSA(api_url, chave)
        url_painel = f"{api_url.rstrip('/')}/painel/"
    else:
        # mesma API, no mesmo processo: autenticação, validação e eventos SSE como em produção
        cliente = ClienteGSA(
            URL_INTERNA,
            chave,
            lambda: httpx.ASGITransport(app=app, raise_app_exceptions=False),
        )
        url_painel = "/painel/"
    contexto = ContextoSimulador(cliente, RepositorioSessoes(), url_painel)
    app.state.simulador = contexto
    app.include_router(router)
    app.mount("/simulador", StaticFiles(directory=PASTA_WEB, html=True), name="simulador")
    return contexto
