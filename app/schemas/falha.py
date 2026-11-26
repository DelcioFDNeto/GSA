from datetime import datetime

from pydantic import Field

from app.models.enums import StatusFalha, TipoFalha
from app.schemas.base import SchemaBase


class FalhaCreate(SchemaBase):
    """Registro manual de situação anormal pelo operador."""

    via_id: int | None = Field(default=None, gt=0)
    descricao: str = Field(min_length=3, max_length=300, examples=["Câmera obstruída por árvore"])


class FalhaResolver(SchemaBase):
    observacao: str | None = Field(default=None, max_length=300)


class FalhaRead(SchemaBase):
    id: int
    cruzamento_id: int
    via_id: int | None
    tipo: TipoFalha
    status: StatusFalha
    descricao: str
    detectada_em: datetime
    resolvida_em: datetime | None
    observacao_resolucao: str | None


class VerificacaoFalhasRead(SchemaBase):
    verificado_em: datetime
    novas_falhas: list[FalhaRead]
