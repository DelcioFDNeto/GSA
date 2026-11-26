from datetime import datetime

from fastapi import APIRouter, Query, Response, status

from app.api.deps import AdministradorOuOperador, DbSession
from app.api.respostas import ERROS_AUTENTICACAO, ERROS_PADRAO
from app.models import OrigemCiclo
from app.schemas.ciclo import CicloGeradoRead, CicloRead
from app.services.ciclo_service import CicloService

router = APIRouter(tags=["Ciclos semafóricos"], responses=ERROS_PADRAO)


@router.post(
    "/cruzamentos/{cruzamento_id}/calcular-ciclo",
    response_model=CicloGeradoRead,
    status_code=status.HTTP_201_CREATED,
    summary="Calcular e gerar ciclo",
    dependencies=[AdministradorOuOperador],
    responses={**ERROS_AUTENTICACAO, 200: {"description": "Prévia calculada (simular=true)"}},
)
def calcular_ciclo(
    cruzamento_id: int,
    db: DbSession,
    response: Response,
    simular: bool = Query(False, description="Só calcula, sem gravar no histórico"),
):
    """RF06–RF12 — calcula demanda, classificação e tempos de verde a partir da última leitura
    de cada via e grava o novo ciclo (201). Com `simular=true` devolve apenas a prévia (200).
    Perfis administrador e operador."""
    ciclo = CicloService(db).gerar(cruzamento_id, OrigemCiclo.MANUAL, persistir=not simular)
    if simular:
        response.status_code = status.HTTP_200_OK
    return ciclo


@router.get(
    "/cruzamentos/{cruzamento_id}/ciclos",
    response_model=list[CicloRead],
    summary="Histórico de ciclos do cruzamento",
)
def listar_ciclos(
    cruzamento_id: int,
    db: DbSession,
    inicio: datetime | None = Query(None, description="Data/hora inicial (ISO 8601)"),
    fim: datetime | None = Query(None, description="Data/hora final (ISO 8601)"),
    limite: int = Query(50, ge=1, le=500),
):
    """RF13 — ciclos calculados, do mais recente para o mais antigo."""
    return CicloService(db).listar(cruzamento_id, inicio, fim, limite)


@router.get("/ciclos/{ciclo_id}", response_model=CicloRead, summary="Detalhar ciclo")
def obter_ciclo(ciclo_id: int, db: DbSession):
    """RF13 — ciclo com horário, veículos, tempos calculados e regra aplicada."""
    return CicloService(db).obter(ciclo_id)
