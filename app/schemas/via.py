from pydantic import Field

from app.models.enums import Direcao
from app.schemas.base import SchemaBase
from app.schemas.semaforo import SemaforoRead


class ViaCreate(SchemaBase):
    nome: str = Field(min_length=1, max_length=120, examples=["Av. Principal — sentido norte"])
    direcao: Direcao
    quantidade_faixas: int = Field(ge=1, le=10, examples=[2])
    estagio: int | None = Field(
        default=None,
        ge=1,
        le=8,
        description="Vias com o mesmo estágio recebem verde juntas; vazio = estágio próprio",
    )


class ViaUpdate(ViaCreate):
    """PUT substitui todos os campos editáveis da via."""


class ViaRead(SchemaBase):
    id: int
    nome: str
    direcao: Direcao
    quantidade_faixas: int
    estagio: int | None
    cruzamento_id: int
    semaforo: SemaforoRead | None = None
