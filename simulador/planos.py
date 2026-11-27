"""Plano de execução dos semáforos simulados a partir do ciclo calculado pelo GSA.

O ciclo do GSA traz, por via, o verde, o amarelo e o vermelho TOTAL da via no ciclo
(`tempoVermelho` = duração do ciclo − verde − amarelo, ou seja, inclui o tempo em que os outros
estágios estão abertos). Para comandar os semáforos é preciso a sequência de estágios e o
entreverde de cada um, reconstruídos aqui com o próprio motor:

- os estágios vêm de `app.motor.agrupar_estagios` (vias do mesmo estágio abrem juntas; vias sem
  estágio formam um estágio próprio), na mesma ordem usada no cálculo;
- o amarelo do estágio é o do ciclo (o maior entre as vias do estágio);
- o vermelho de segurança — todas as vias no vermelho antes do próximo estágio — é o maior
  `tempoVermelho` CONFIGURADO nos semáforos do estágio (`Estagio.tempo_vermelho`).

A soma de verde + amarelo + vermelho de segurança dos estágios precisa fechar com a duração do
ciclo do GSA, e o vermelho total de cada via precisa fechar com o `tempoVermelho` devolvido;
divergências (ex.: semáforo editado depois do cálculo) voltam como aviso.

Os planos de tempo fixo usados na comparação também saem do motor (`PlanoFixo` e a regra do
cruzamento com a demanda média): o simulador não tem algoritmo de temporização próprio.
"""

from collections.abc import Sequence
from typing import Any

from app.motor import (
    DistribuicaoProporcional,
    EntradaVia,
    FaixasFluxo,
    PlanoFixo,
    RegraTemporizacao,
    ResultadoCalculo,
    Webster,
    agrupar_estagios,
    calcular_ciclo,
)

# Movimentos em linha reta: vias do mesmo eixo não se cruzam; de eixos diferentes, sim.
EIXO_DA_DIRECAO = {"norte": "ns", "sul": "ns", "leste": "lo", "oeste": "lo"}


class PlanoInvalido(ValueError):
    """O ciclo não pode ser convertido em um plano executável com segurança."""


def semaforo_ativo(via: dict) -> bool:
    semaforo = via.get("semaforo")
    return bool(semaforo) and semaforo.get("status") == "ativo"


def _entrada(via: dict, veiculos: int) -> EntradaVia:
    semaforo = via["semaforo"]
    return EntradaVia(
        via_id=via["id"],
        quantidade_veiculos=veiculos,
        quantidade_faixas=via["quantidadeFaixas"],
        tempo_minimo_verde=semaforo["tempoMinimoVerde"],
        tempo_maximo_verde=semaforo["tempoMaximoVerde"],
        tempo_amarelo=semaforo["tempoAmarelo"],
        tempo_vermelho=semaforo["tempoVermelho"],
        estagio=via.get("estagio"),
    )


def entradas(vias: Sequence[dict], contagens: dict[int, int] | None = None) -> list[EntradaVia]:
    """Entradas do motor para as vias com semáforo ativo, como o CicloService as monta."""
    contagens = contagens or {}
    return [_entrada(via, contagens.get(via["id"], 0)) for via in vias if semaforo_ativo(via)]


def faixas_de_fluxo(parametros: dict) -> FaixasFluxo:
    return FaixasFluxo(
        baixo=parametros["limiteFluxoBaixo"],
        moderado=parametros["limiteFluxoModerado"],
        alto=parametros["limiteFluxoAlto"],
    )


def regra_do_cruzamento(cruzamento: dict, parametros: dict) -> RegraTemporizacao:
    """A mesma escolha de ParametroService.regra_para, a partir dos dados da API REST."""
    if cruzamento.get("regraTemporizacao") == "webster":
        return Webster(
            fluxo_saturacao_por_faixa=parametros["fluxoSaturacaoPorFaixa"],
            intervalo_contagem=parametros["intervaloContagem"],
            ciclo_minimo=parametros["cicloMinimo"],
            ciclo_maximo=parametros["cicloMaximo"],
        )
    return DistribuicaoProporcional()


def duracao_do_ciclo(cruzamento: dict, parametros: dict) -> int:
    """Duração própria do cruzamento ou, se vazia, a do parâmetro global (RF16)."""
    return cruzamento.get("duracaoCiclo") or parametros["duracaoCiclo"]


def _rotulo(chave: str, vias: Sequence[EntradaVia], nomes: dict[int, str]) -> str:
    if chave.startswith("e"):
        return f"Estágio {chave[1:]}"
    return nomes.get(vias[0].via_id, f"Via {vias[0].via_id}")


def plano_do_ciclo(ciclo: dict, vias: Sequence[dict], origem: str = "gsa") -> dict[str, Any]:
    """Converte um ciclo no formato de `cicloGerado` em estágios executáveis."""
    tempos = {t["viaId"]: t for t in ciclo["tempos"]}
    if not tempos:
        raise PlanoInvalido("o ciclo não tem tempos de semáforo")
    por_id = {via["id"]: via for via in vias}
    desconhecidas = [via_id for via_id in tempos if not por_id.get(via_id, {}).get("semaforo")]
    if desconhecidas:
        raise PlanoInvalido(f"vias {desconhecidas} do ciclo sem semáforo cadastrado")

    # Mesma ordem do cálculo (vias por id), para os estágios abrirem na sequência do motor
    calculadas = [
        _entrada(por_id[via_id], tempos[via_id]["quantidadeVeiculos"]) for via_id in tempos
    ]
    nomes = {via["id"]: via.get("nome", f"Via {via['id']}") for via in vias}
    estagios = []
    for estagio in agrupar_estagios(calculadas):
        verdes = {tempos[v.via_id]["tempoVerde"] for v in estagio.vias}
        if len(verdes) != 1:
            raise PlanoInvalido(f"vias do estágio {estagio.chave} com verdes diferentes: {verdes}")
        estagios.append(
            {
                "chave": estagio.chave,
                "rotulo": _rotulo(estagio.chave, estagio.vias, nomes),
                "vias": [v.via_id for v in estagio.vias],
                "verde": verdes.pop(),
                "amarelo": max(tempos[v.via_id]["tempoAmarelo"] for v in estagio.vias),
                "vermelho": estagio.tempo_vermelho,  # vermelho de segurança configurado
            }
        )

    duracao = sum(e["verde"] + e["amarelo"] + e["vermelho"] for e in estagios)
    avisos = []
    if duracao != ciclo["duracaoTotal"]:
        avisos.append(
            f"Duração reconstruída ({duracao} s) difere da do GSA ({ciclo['duracaoTotal']} s): "
            "a configuração dos semáforos mudou depois do cálculo."
        )
    for estagio in estagios:
        vermelho_total = duracao - estagio["verde"] - estagio["amarelo"]
        for via_id in estagio["vias"]:
            if tempos[via_id]["tempoVermelho"] != vermelho_total:
                avisos.append(
                    f"Via {via_id}: vermelho total {vermelho_total} s no plano e "
                    f"{tempos[via_id]['tempoVermelho']} s no ciclo do GSA."
                )

    return {
        "origem": origem,
        "cicloId": ciclo.get("id"),
        "modoOperacao": ciclo.get("modoOperacao", "adaptativo"),
        "regra": ciclo.get("regraAplicada"),
        "motivoContingencia": ciclo.get("motivoContingencia"),
        "grauSaturacao": ciclo.get("grauSaturacao"),
        "duracaoCicloConfigurada": ciclo.get("duracaoCicloConfigurada"),
        "duracao": duracao,
        "duracaoGsa": ciclo["duracaoTotal"],
        "estagios": estagios,
        "tempos": {
            str(via_id): {
                "nome": t.get("nomeVia") or nomes.get(via_id),
                "verde": t["tempoVerde"],
                "amarelo": t["tempoAmarelo"],
                "vermelho": t["tempoVermelho"],
                "veiculos": t["quantidadeVeiculos"],
                "demanda": t["demandaPercentual"],
                "classificacao": t["classificacaoFluxo"],
                "ajuste": t["ajusteAplicado"],
            }
            for via_id, t in tempos.items()
        },
        "viasIgnoradas": ciclo.get("viasIgnoradas", []),
        "avisos": avisos,
    }


def ciclo_do_resultado(resultado: ResultadoCalculo, vias: Sequence[dict], modo: str) -> dict:
    """Resultado do motor no formato de `cicloGerado` (sem gravar nada no GSA)."""
    nomes = {via["id"]: via.get("nome") for via in vias}
    return {
        "id": None,
        "modoOperacao": modo,
        "regraAplicada": resultado.regra,
        "duracaoCicloConfigurada": resultado.duracao_ciclo_configurada,
        "duracaoTotal": resultado.duracao_total,
        "grauSaturacao": resultado.grau_saturacao,
        "motivoContingencia": None,
        "tempos": [
            {
                "viaId": t.via_id,
                "nomeVia": nomes.get(t.via_id),
                "quantidadeVeiculos": t.quantidade_veiculos,
                "demandaPercentual": round(t.demanda * 100, 1),
                "classificacaoFluxo": t.classificacao.value,
                "tempoVerde": t.tempo_verde,
                "tempoAmarelo": t.tempo_amarelo,
                "tempoVermelho": t.tempo_vermelho,
                "ajusteAplicado": t.ajuste.value,
            }
            for t in resultado.tempos
        ],
    }


def _calcular(vias, contagens, duracao, faixas, regra, origem) -> dict:
    calculaveis = entradas(vias, contagens)
    if not calculaveis:
        raise PlanoInvalido("o cruzamento não tem semáforo ativo")
    resultado = calcular_ciclo(calculaveis, duracao, faixas, regra)
    return plano_do_ciclo(ciclo_do_resultado(resultado, vias, "tempo_fixo"), vias, origem)


def plano_fixo(vias: Sequence[dict], duracao: int, faixas: FaixasFluxo) -> dict:
    """Plano fixo do GSA (verde igual entre os estágios): o do modo de segurança, que um
    controlador convencional executaria sem o controle adaptativo."""
    return _calcular(vias, {}, duracao, faixas, PlanoFixo(), "tempo_fixo")


def plano_ajustado(cruzamento: dict, parametros: dict, taxas: dict[int, float]) -> dict:
    """Plano fixo calculado uma única vez pela regra do cruzamento com a demanda média
    (veículos/hora de cada via) — como um técnico programaria um semáforo convencional."""
    janela = parametros["intervaloContagem"]
    contagens = {via_id: round(max(taxa, 0) * janela / 3600) for via_id, taxa in taxas.items()}
    return _calcular(
        cruzamento["vias"],
        contagens,
        duracao_do_ciclo(cruzamento, parametros),
        faixas_de_fluxo(parametros),
        regra_do_cruzamento(cruzamento, parametros),
        "tempo_fixo_ajustado",
    )


def verificar_vias(vias: Sequence[dict]) -> list[str]:
    """Avisos sobre vias que o simulador não representa ou estágios inseguros."""
    avisos = []
    for via in vias:
        if via["direcao"] not in EIXO_DA_DIRECAO:
            avisos.append(
                f"{via['nome']}: direção '{via['direcao']}' não é representada no desenho "
                "(só norte, sul, leste e oeste); a via fica sem leitura."
            )
        if not semaforo_ativo(via):
            avisos.append(f"{via['nome']}: sem semáforo ativo, fica fora do cálculo do GSA.")
    por_id = {via["id"]: via for via in vias}
    calculaveis = entradas(vias)
    if calculaveis:
        for estagio in agrupar_estagios(calculaveis):
            eixos = {EIXO_DA_DIRECAO.get(por_id[v.via_id]["direcao"]) for v in estagio.vias}
            if len(eixos) > 1:
                avisos.append(
                    f"Estágio {estagio.chave} junta movimentos que se cruzam: o controlador "
                    "simulado recusa planos com esse estágio."
                )
    return avisos
