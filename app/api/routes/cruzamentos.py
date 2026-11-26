from fastapi import APIRouter, Query, status

from app.api.deps import ApenasAdministrador, DbSession
from app.api.respostas import ERROS_AUTENTICACAO, ERROS_PADRAO
from app.models import StatusCruzamento
from app.schemas.cruzamento import (
    CruzamentoCreate,
    CruzamentoDetalhe,
    CruzamentoRead,
    CruzamentoUpdate,
)
from app.services.cruzamento_service import CruzamentoService

router = APIRouter(prefix="/cruzamentos", tags=["Cruzamentos"], responses=ERROS_PADRAO)
ADMIN = {"dependencies": [ApenasAdministrador], "responses": ERROS_AUTENTICACAO}


@router.post(
    "",
    response_model=CruzamentoRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar cruzamento",
    **ADMIN,
)
def criar_cruzamento(dados: CruzamentoCreate, db: DbSession):
    """RF01 — cadastra um cruzamento. Perfil administrador."""
    return CruzamentoService(db).criar(dados)


@router.get("", response_model=list[CruzamentoRead], summary="Listar cruzamentos")
def listar_cruzamentos(
    db: DbSession,
    status_filtro: StatusCruzamento | None = Query(None, alias="status"),
):
    """Lista os cruzamentos, opcionalmente filtrando por status."""
    return CruzamentoService(db).listar(status_filtro)


@router.get("/{cruzamento_id}", response_model=CruzamentoDetalhe, summary="Detalhar cruzamento")
def obter_cruzamento(cruzamento_id: int, db: DbSession):
    """Detalha um cruzamento com suas vias e semáforos."""
    return CruzamentoService(db).obter_detalhe(cruzamento_id)


@router.put(
    "/{cruzamento_id}", response_model=CruzamentoRead, summary="Atualizar cruzamento", **ADMIN
)
def atualizar_cruzamento(cruzamento_id: int, dados: CruzamentoUpdate, db: DbSession):
    """Atualiza os dados do cruzamento. Perfil administrador."""
    return CruzamentoService(db).atualizar(cruzamento_id, dados)


@router.post(
    "/{cruzamento_id}/ativar", response_model=CruzamentoRead, summary="Ativar cruzamento", **ADMIN
)
def ativar_cruzamento(cruzamento_id: int, db: DbSession):
    """RF17 — reativa o cruzamento. Perfil administrador."""
    return CruzamentoService(db).ativar(cruzamento_id)


@router.post(
    "/{cruzamento_id}/desativar",
    response_model=CruzamentoRead,
    summary="Desativar cruzamento",
    **ADMIN,
)
def desativar_cruzamento(cruzamento_id: int, db: DbSession):
    """RF17 — desativa o cruzamento sem apagar registros. Perfil administrador."""
    return CruzamentoService(db).desativar(cruzamento_id)


@router.delete(
    "/{cruzamento_id}",
    response_model=CruzamentoRead,
    summary="Excluir cruzamento (desativação lógica)",
    **ADMIN,
)
def excluir_cruzamento(cruzamento_id: int, db: DbSession):
    """RF17 — a exclusão é lógica: o cruzamento fica inativo e o histórico é preservado."""
    return CruzamentoService(db).desativar(cruzamento_id)
