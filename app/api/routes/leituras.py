from datetime import datetime

from fastapi import APIRouter, Query, status

from app.api.deps import DbSession, SistemaDeteccao
from app.api.respostas import ERROS_AUTENTICACAO, ERROS_PADRAO
from app.schemas.leitura import (
    LeituraLoteCreate,
    LeituraLoteResultado,
    LeituraRead,
    LeituraViaCreate,
)
from app.services.leitura_service import LeituraService

router = APIRouter(tags=["Leituras de tráfego"], responses=ERROS_PADRAO)
DETECCAO = {"dependencies": [SistemaDeteccao], "responses": ERROS_AUTENTICACAO}


@router.post(
    "/cruzamentos/{cruzamento_id}/leituras",
    response_model=LeituraLoteResultado,
    status_code=status.HTTP_201_CREATED,
    summary="Receber leituras do cruzamento (lote)",
    **DETECCAO,
)
def registrar_leituras_do_cruzamento(cruzamento_id: int, dados: LeituraLoteCreate, db: DbSession):
    """RF04/RF05/RF12 — recebe as contagens do sistema de detecção, grava cada leitura e gera
    um novo ciclo semafórico. Autenticação: cabeçalho `X-API-Key` ou token Bearer."""
    leituras, ciclo, avisos = LeituraService(db).registrar_lote(cruzamento_id, dados)
    return LeituraLoteResultado(
        cruzamento_id=cruzamento_id,
        quantidade_registrada=len(leituras),
        leituras=[LeituraRead.model_validate(leitura) for leitura in leituras],
        ciclo_gerado=ciclo,
        avisos=avisos,
    )


@router.get(
    "/cruzamentos/{cruzamento_id}/leituras",
    response_model=list[LeituraRead],
    summary="Listar leituras do cruzamento",
)
def listar_leituras_do_cruzamento(
    cruzamento_id: int,
    db: DbSession,
    inicio: datetime | None = Query(None, description="Data/hora inicial (ISO 8601)"),
    fim: datetime | None = Query(None, description="Data/hora final (ISO 8601)"),
    via_id: int | None = Query(None, alias="viaId", description="Filtrar por uma via"),
    limite: int = Query(100, ge=1, le=1000),
):
    """RF15 — histórico de leituras do cruzamento, da mais recente para a mais antiga."""
    return LeituraService(db).listar_por_cruzamento(cruzamento_id, inicio, fim, via_id, limite)


@router.post(
    "/vias/{via_id}/leituras",
    response_model=LeituraRead,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar leitura de uma via",
    **DETECCAO,
)
def registrar_leitura_da_via(via_id: int, dados: LeituraViaCreate, db: DbSession):
    """RF05 — registra a contagem de uma única via (não gera ciclo)."""
    return LeituraService(db).registrar_por_via(via_id, dados.quantidade_veiculos)


@router.get(
    "/vias/{via_id}/leituras", response_model=list[LeituraRead], summary="Listar leituras da via"
)
def listar_leituras_da_via(
    via_id: int,
    db: DbSession,
    inicio: datetime | None = Query(None, description="Data/hora inicial (ISO 8601)"),
    fim: datetime | None = Query(None, description="Data/hora final (ISO 8601)"),
    limite: int = Query(100, ge=1, le=1000),
):
    """RF15 — leituras da via, da mais recente para a mais antiga."""
    return LeituraService(db).listar_por_via(via_id, inicio, fim, limite)
