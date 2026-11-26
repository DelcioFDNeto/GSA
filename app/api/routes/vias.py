from fastapi import APIRouter, status

from app.api.deps import ApenasAdministrador, DbSession
from app.api.respostas import ERROS_AUTENTICACAO, ERROS_PADRAO
from app.schemas.via import ViaCreate, ViaRead, ViaUpdate
from app.services.via_service import ViaService

router = APIRouter(tags=["Vias"], responses=ERROS_PADRAO)
ADMIN = {"dependencies": [ApenasAdministrador], "responses": ERROS_AUTENTICACAO}


@router.post(
    "/cruzamentos/{cruzamento_id}/vias",
    response_model=ViaRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar via",
    **ADMIN,
)
def criar_via(cruzamento_id: int, dados: ViaCreate, db: DbSession):
    """RF02 — cadastra uma via no cruzamento. Perfil administrador."""
    return ViaService(db).criar(cruzamento_id, dados)


@router.get(
    "/cruzamentos/{cruzamento_id}/vias", response_model=list[ViaRead], summary="Listar vias"
)
def listar_vias(cruzamento_id: int, db: DbSession):
    """Lista as vias do cruzamento com seus semáforos."""
    return ViaService(db).listar_por_cruzamento(cruzamento_id)


@router.get("/vias/{via_id}", response_model=ViaRead, summary="Detalhar via")
def obter_via(via_id: int, db: DbSession):
    return ViaService(db).obter(via_id)


@router.put("/vias/{via_id}", response_model=ViaRead, summary="Atualizar via", **ADMIN)
def atualizar_via(via_id: int, dados: ViaUpdate, db: DbSession):
    return ViaService(db).atualizar(via_id, dados)
