from fastapi import APIRouter, Query, status

from app.api.deps import AdministradorOuOperador, DbSession
from app.api.respostas import ERROS_AUTENTICACAO, ERROS_PADRAO
from app.db.types import agora_utc
from app.models import StatusFalha, TipoFalha
from app.schemas.falha import FalhaCreate, FalhaRead, FalhaResolver, VerificacaoFalhasRead
from app.services.falha_service import FalhaService

router = APIRouter(tags=["Falhas"], responses=ERROS_PADRAO)
OPERADOR = {"dependencies": [AdministradorOuOperador], "responses": ERROS_AUTENTICACAO}


@router.get("/falhas", response_model=list[FalhaRead], summary="Listar falhas")
def listar_falhas(
    db: DbSession,
    status_filtro: StatusFalha | None = Query(None, alias="status"),
    tipo: TipoFalha | None = None,
    cruzamento_id: int | None = Query(None, alias="cruzamentoId"),
    limite: int = Query(100, ge=1, le=1000),
):
    """RF18 — falhas e situações anormais, das mais recentes para as mais antigas."""
    return FalhaService(db).listar(cruzamento_id, status_filtro, tipo, limite)


@router.get(
    "/cruzamentos/{cruzamento_id}/falhas",
    response_model=list[FalhaRead],
    summary="Listar falhas do cruzamento",
)
def listar_falhas_do_cruzamento(
    cruzamento_id: int,
    db: DbSession,
    status_filtro: StatusFalha | None = Query(None, alias="status"),
    limite: int = Query(100, ge=1, le=1000),
):
    return FalhaService(db).listar(cruzamento_id, status_filtro, None, limite)


@router.post(
    "/cruzamentos/{cruzamento_id}/falhas",
    response_model=FalhaRead,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar falha manualmente",
    **OPERADOR,
)
def registrar_falha(cruzamento_id: int, dados: FalhaCreate, db: DbSession):
    """RF18 — registro de situação anormal pelo operador."""
    return FalhaService(db).registrar_manual(cruzamento_id, dados)


@router.post(
    "/falhas/{falha_id}/resolver",
    response_model=FalhaRead,
    summary="Resolver falha",
    **OPERADOR,
)
def resolver_falha(falha_id: int, dados: FalhaResolver, db: DbSession):
    return FalhaService(db).resolver(falha_id, dados.observacao)


@router.post(
    "/falhas/verificar",
    response_model=VerificacaoFalhasRead,
    summary="Verificar ausência de leituras agora",
    **OPERADOR,
)
def verificar_falhas(db: DbSession):
    """RF18 — executa na hora a mesma verificação que a API faz periodicamente."""
    agora = agora_utc()
    novas = FalhaService(db).verificar_ausencia_leituras(agora)
    return VerificacaoFalhasRead(verificado_em=agora, novas_falhas=novas)
