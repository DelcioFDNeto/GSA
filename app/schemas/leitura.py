from datetime import datetime

from pydantic import Field, field_validator

from app.schemas.base import SchemaBase
from app.schemas.ciclo import CicloGeradoRead


class LeituraItem(SchemaBase):
    via_id: int = Field(gt=0)
    quantidade_veiculos: int = Field(ge=0, le=10_000)


class LeituraLoteCreate(SchemaBase):
    """Payload enviado pelo sistema de detecção (RF04)."""

    cruzamento_id: int = Field(gt=0)
    leituras: list[LeituraItem] = Field(min_length=1)

    @field_validator("leituras")
    @classmethod
    def vias_sem_repeticao(cls, leituras: list[LeituraItem]) -> list[LeituraItem]:
        ids = [item.via_id for item in leituras]
        if len(ids) != len(set(ids)):
            raise ValueError("cada via pode aparecer apenas uma vez por lote de leituras")
        return leituras

    model_config = SchemaBase.model_config | {
        "json_schema_extra": {
            "examples": [
                {
                    "cruzamentoId": 1,
                    "leituras": [
                        {"viaId": 1, "quantidadeVeiculos": 28},
                        {"viaId": 2, "quantidadeVeiculos": 9},
                    ],
                }
            ]
        }
    }


class LeituraViaCreate(SchemaBase):
    quantidade_veiculos: int = Field(ge=0, le=10_000, examples=[12])


class LeituraRead(SchemaBase):
    id: int
    via_id: int
    quantidade_veiculos: int
    data_hora: datetime


class LeituraLoteResultado(SchemaBase):
    cruzamento_id: int
    quantidade_registrada: int
    leituras: list[LeituraRead]
    ciclo_gerado: CicloGeradoRead | None
    avisos: list[str]
