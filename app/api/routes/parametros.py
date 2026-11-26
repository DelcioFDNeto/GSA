from fastapi import APIRouter

from app.api.deps import ApenasAdministrador, DbSession
from app.api.respostas import ERROS_AUTENTICACAO, ERROS_PADRAO
from app.schemas.parametros import ParametrosRead, ParametrosUpdate
from app.services.parametro_service import ParametroService

router = APIRouter(prefix="/parametros", tags=["Parâmetros"], responses=ERROS_PADRAO)


@router.get("", response_model=ParametrosRead, summary="Consultar parâmetros do algoritmo")
def obter_parametros(db: DbSession):
    """RF16 — faixas de fluxo, verde mínimo/máximo padrão, duração do ciclo e limite de tempo
    sem leitura."""
    return ParametroService(db).obter()


@router.put(
    "",
    response_model=ParametrosRead,
    summary="Alterar parâmetros do algoritmo",
    dependencies=[ApenasAdministrador],
    responses=ERROS_AUTENTICACAO,
)
def atualizar_parametros(dados: ParametrosUpdate, db: DbSession):
    """RF16 — novos valores valem para os próximos cálculos. Perfil administrador."""
    return ParametroService(db).atualizar(dados)
