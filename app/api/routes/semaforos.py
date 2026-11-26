from fastapi import APIRouter, status

from app.api.deps import ApenasAdministrador, DbSession
from app.api.respostas import ERROS_AUTENTICACAO, ERROS_PADRAO
from app.schemas.semaforo import SemaforoCreate, SemaforoRead, SemaforoUpdate
from app.services.via_service import SemaforoService

router = APIRouter(tags=["Semáforos"], responses=ERROS_PADRAO)
ADMIN = {"dependencies": [ApenasAdministrador], "responses": ERROS_AUTENTICACAO}


@router.post(
    "/vias/{via_id}/semaforo",
    response_model=SemaforoRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar semáforo da via",
    **ADMIN,
)
def criar_semaforo(via_id: int, dados: SemaforoCreate, db: DbSession):
    """RF03 — cadastra o semáforo da via (um por via). Tempos de verde omitidos usam os
    valores padrão dos parâmetros. Perfil administrador."""
    return SemaforoService(db).criar(via_id, dados)


@router.get("/vias/{via_id}/semaforo", response_model=SemaforoRead, summary="Obter semáforo da via")
def obter_semaforo_da_via(via_id: int, db: DbSession):
    return SemaforoService(db).obter_por_via(via_id)


@router.get(
    "/cruzamentos/{cruzamento_id}/semaforos",
    response_model=list[SemaforoRead],
    summary="Listar semáforos do cruzamento",
)
def listar_semaforos(cruzamento_id: int, db: DbSession):
    return SemaforoService(db).listar_por_cruzamento(cruzamento_id)


@router.get("/semaforos/{semaforo_id}", response_model=SemaforoRead, summary="Detalhar semáforo")
def obter_semaforo(semaforo_id: int, db: DbSession):
    return SemaforoService(db).obter(semaforo_id)


@router.put(
    "/semaforos/{semaforo_id}",
    response_model=SemaforoRead,
    summary="Atualizar semáforo",
    **ADMIN,
)
def atualizar_semaforo(semaforo_id: int, dados: SemaforoUpdate, db: DbSession):
    """Atualiza tempos mínimo/máximo de verde, amarelo, vermelho e status."""
    return SemaforoService(db).atualizar(semaforo_id, dados)
