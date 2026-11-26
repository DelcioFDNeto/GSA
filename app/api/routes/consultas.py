from datetime import datetime

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.api.respostas import ERROS_PADRAO
from app.schemas.consulta import HistoricoRead, SituacaoRead
from app.services.consulta_service import ConsultaService

router = APIRouter(tags=["Consultas"], responses=ERROS_PADRAO)


@router.get(
    "/cruzamentos/{cruzamento_id}/situacao",
    response_model=SituacaoRead,
    summary="Situação atual do cruzamento",
)
def situacao(cruzamento_id: int, db: DbSession):
    """RF14 — veículos atuais, classificação de fluxo, tempo de verde recomendado, última
    leitura de cada via e falhas abertas."""
    return ConsultaService(db).situacao(cruzamento_id)


@router.get(
    "/cruzamentos/{cruzamento_id}/historico",
    response_model=HistoricoRead,
    summary="Histórico de trânsito do cruzamento",
)
def historico(
    cruzamento_id: int,
    db: DbSession,
    inicio: datetime | None = Query(None, description="Padrão: 24 horas antes do fim"),
    fim: datetime | None = Query(None, description="Padrão: agora"),
):
    """RF15 — leituras e ciclos do período resumidos por via (média, mínimo e máximo)."""
    return ConsultaService(db).historico(cruzamento_id, inicio, fim)
