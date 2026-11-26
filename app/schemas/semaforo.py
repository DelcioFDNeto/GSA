from pydantic import Field, model_validator

from app.models.enums import StatusSemaforo
from app.schemas.base import SchemaBase


class _TemposSemaforo(SchemaBase):
    tempo_amarelo: int = Field(gt=0, le=10, description="Segundos", examples=[3])
    tempo_vermelho: int = Field(
        default=0,
        ge=0,
        le=60,
        description="Vermelho de segurança após o amarelo, em segundos",
        examples=[2],
    )
    status: StatusSemaforo = StatusSemaforo.ATIVO

    @model_validator(mode="after")
    def verificar_limites_verde(self):
        minimo = getattr(self, "tempo_minimo_verde", None)
        maximo = getattr(self, "tempo_maximo_verde", None)
        if minimo is not None and maximo is not None and maximo < minimo:
            raise ValueError("tempoMaximoVerde deve ser maior ou igual a tempoMinimoVerde")
        return self


class SemaforoCreate(_TemposSemaforo):
    """Tempos de verde omitidos usam os valores padrão dos parâmetros (RF16)."""

    tempo_minimo_verde: int | None = Field(
        default=None, gt=0, le=300, description="Segundos", examples=[20]
    )
    tempo_maximo_verde: int | None = Field(
        default=None, gt=0, le=300, description="Segundos", examples=[70]
    )


class SemaforoUpdate(_TemposSemaforo):
    """PUT substitui todos os tempos e o status do semáforo."""

    tempo_minimo_verde: int = Field(gt=0, le=300, description="Segundos", examples=[20])
    tempo_maximo_verde: int = Field(gt=0, le=300, description="Segundos", examples=[70])


class SemaforoRead(SchemaBase):
    id: int
    via_id: int
    tempo_minimo_verde: int
    tempo_maximo_verde: int
    tempo_amarelo: int
    tempo_vermelho: int
    status: StatusSemaforo
