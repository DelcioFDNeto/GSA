import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.deps import DbSession
from app.api.routes import (
    auth,
    ciclos,
    consultas,
    cruzamentos,
    eventos,
    falhas,
    leituras,
    parametros,
    semaforos,
    vias,
)
from app.core.config import get_settings
from app.core.exceptions import ErroDominio
from app.db.session import SessionLocal
from app.schemas.base import ErroResposta
from app.services.falha_service import FalhaService

logger = logging.getLogger("gsa")
settings = get_settings()

DESCRICAO = """
Backend do **Sistema de Gestão Semafórica Adaptativa**: recebe a contagem de veículos por via
(enviada por um sistema externo de visão computacional, ex.: YOLO), aplica regras de negócio
configuráveis e calcula o tempo de verde recomendado para cada semáforo do cruzamento.

A decisão **não usa inteligência artificial**: o tempo de verde disponível é distribuído de forma
proporcional à demanda, respeitando os tempos mínimo e máximo de cada semáforo.

**Autenticação:** consultas (GET) são abertas. Cadastros e parâmetros exigem o perfil
*administrador*; cálculo manual de ciclo e tratamento de falhas aceitam *operador*. Use
`POST /auth/login` (ou o botão **Authorize**). O sistema de detecção envia leituras com o
cabeçalho `X-API-Key`.
"""

TAGS = [
    {"name": "Autenticação", "description": "Login, usuário logado e cadastro de usuários."},
    {"name": "Cruzamentos", "description": "Cadastro, consulta, ativação e desativação."},
    {"name": "Vias", "description": "Vias que compõem cada cruzamento."},
    {"name": "Semáforos", "description": "Semáforo de cada via e seus tempos configurados."},
    {"name": "Leituras de tráfego", "description": "Contagens de veículos recebidas por via."},
    {"name": "Ciclos semafóricos", "description": "Cálculo, gravação e histórico de ciclos."},
    {"name": "Consultas", "description": "Situação atual e histórico de trânsito."},
    {"name": "Parâmetros", "description": "Configuração do algoritmo de temporização."},
    {"name": "Falhas", "description": "Ausência de leituras e outras situações anormais."},
    {"name": "Tempo real", "description": "Eventos (SSE) para o painel ao vivo em /painel."},
    {"name": "Sistema", "description": "Verificação de funcionamento da API."},
]


def _verificar_falhas_uma_vez() -> None:
    with SessionLocal() as db:
        novas = FalhaService(db).verificar_ausencia_leituras()
        if novas:
            logger.warning("%d nova(s) falha(s) de ausência de leitura registrada(s)", len(novas))


async def _verificar_falhas_periodicamente(intervalo: int) -> None:
    while True:
        await asyncio.sleep(intervalo)
        try:
            await run_in_threadpool(_verificar_falhas_uma_vez)
        except Exception:  # a tarefa não pode parar por causa de uma falha pontual
            logger.exception("Erro na verificação periódica de falhas")


@contextlib.asynccontextmanager
async def ciclo_de_vida(_app: FastAPI) -> AsyncIterator[None]:
    tarefa = None
    if settings.intervalo_verificacao_falhas > 0:
        tarefa = asyncio.create_task(
            _verificar_falhas_periodicamente(settings.intervalo_verificacao_falhas)
        )
    yield
    if tarefa is not None:
        tarefa.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await tarefa


app = FastAPI(
    title=settings.nome_aplicacao,
    version=settings.versao,
    description=DESCRICAO,
    openapi_tags=TAGS,
    lifespan=ciclo_de_vida,
)

for modulo in (
    auth,
    cruzamentos,
    vias,
    semaforos,
    leituras,
    ciclos,
    consultas,
    parametros,
    falhas,
    eventos,
):
    app.include_router(modulo.router)

PASTA_PAINEL = Path(__file__).parent / "painel"
app.mount("/painel", StaticFiles(directory=PASTA_PAINEL, html=True), name="painel")


@app.get("/", include_in_schema=False)
def inicio() -> RedirectResponse:
    return RedirectResponse("/painel/")


def _erro(
    status: int,
    titulo: str,
    mensagem: str,
    detalhes: list[str] | None = None,
    cabecalhos: dict[str, str] | None = None,
):
    corpo = ErroResposta(status=status, erro=titulo, mensagem=mensagem, detalhes=detalhes)
    return JSONResponse(
        status_code=status, content=corpo.model_dump(mode="json"), headers=cabecalhos
    )


@app.exception_handler(ErroDominio)
async def tratar_erro_dominio(_request: Request, exc: ErroDominio):
    return _erro(exc.status_code, exc.titulo, exc.mensagem, exc.detalhes, exc.cabecalhos)


@app.exception_handler(RequestValidationError)
async def tratar_erro_validacao(_request: Request, exc: RequestValidationError):
    """RNF04/RNF06 — dados inválidos retornam 400 com a lista de campos rejeitados."""
    detalhes = []
    for erro in exc.errors():
        if erro["type"] == "json_invalid":
            detalhes.append("JSON malformado")
            continue
        campo = ".".join(str(parte) for parte in erro["loc"] if parte != "body")
        mensagem = erro["msg"].removeprefix("Value error, ")
        detalhes.append(f"{campo}: {mensagem}" if campo else mensagem)
    return _erro(400, "Dados inválidos", "A requisição contém dados inválidos", detalhes)


@app.exception_handler(StarletteHTTPException)
async def tratar_http_exception(_request: Request, exc: StarletteHTTPException):
    mensagens = {404: "Rota não encontrada", 405: "Método HTTP não permitido nesta rota"}
    titulo = "Recurso não encontrado" if exc.status_code == 404 else "Erro na requisição"
    return _erro(
        exc.status_code,
        titulo,
        mensagens.get(exc.status_code, str(exc.detail)),
        cabecalhos=getattr(exc, "headers", None),
    )


@app.exception_handler(Exception)
async def tratar_erro_inesperado(_request: Request, exc: Exception):
    logger.exception("Erro não tratado", exc_info=exc)
    return _erro(500, "Erro interno", "Erro inesperado no servidor")


@app.get("/health", tags=["Sistema"], summary="Verificar saúde da API")
def health(db: DbSession) -> dict[str, str]:
    """Confirma que a API está no ar e que o banco de dados responde."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "versao": settings.versao}


def _openapi_personalizado() -> dict:
    """Troca o 422 padrão do FastAPI pelo 400 usado pela API (RNF06)."""
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
    )
    for operacoes in schema["paths"].values():
        for operacao in operacoes.values():
            operacao.get("responses", {}).pop("422", None)
    componentes = schema.get("components", {}).get("schemas", {})
    componentes.pop("HTTPValidationError", None)
    componentes.pop("ValidationError", None)
    app.openapi_schema = schema
    return schema


app.openapi = _openapi_personalizado

if settings.simulador_habilitado:
    # Gêmeo digital para demonstração: câmera sintética + semáforos controlados pelo GSA.
    # Importado só quando ligado: a API não depende do simulador nem de deteccao/.
    from simulador.servidor import montar_simulador

    montar_simulador(app, settings.simulador_api_url)
