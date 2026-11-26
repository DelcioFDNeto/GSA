from datetime import datetime

from pydantic import Field

from app.models.enums import RegraTemporizacao, StatusCruzamento
from app.schemas.base import SchemaBase
from app.schemas.via import ViaRead


class CruzamentoCreate(SchemaBase):
    nome: str = Field(min_length=1, max_length=120, examples=["Av. Principal x Rua Secundária"])
    latitude: float = Field(ge=-90, le=90, examples=[-15.7939])
    longitude: float = Field(ge=-180, le=180, examples=[-47.8828])
    status: StatusCruzamento = StatusCruzamento.ATIVO
    duracao_ciclo: int | None = Field(
        default=None,
        ge=30,
        le=300,
        description="Duração do ciclo deste cruzamento em segundos; vazio usa o parâmetro global",
    )
    regra_temporizacao: RegraTemporizacao = Field(
        default=RegraTemporizacao.PROPORCIONAL,
        description="proporcional: ciclo fixo; webster: ciclo ótimo que varia com a demanda",
    )


class CruzamentoUpdate(CruzamentoCreate):
    """PUT substitui todos os campos editáveis do cruzamento."""


class CruzamentoRead(SchemaBase):
    id: int
    nome: str
    latitude: float
    longitude: float
    status: StatusCruzamento
    duracao_ciclo: int | None
    regra_temporizacao: RegraTemporizacao
    criado_em: datetime
    atualizado_em: datetime


class CruzamentoDetalhe(CruzamentoRead):
    vias: list[ViaRead]
