from datetime import datetime

from pydantic import Field, model_validator

from app.schemas.base import SchemaBase


class ParametrosUpdate(SchemaBase):
    duracao_ciclo: int = Field(ge=30, le=300, description="Segundos", examples=[90])
    limite_fluxo_baixo: float = Field(gt=0, description="Veículos por faixa", examples=[5])
    limite_fluxo_moderado: float = Field(gt=0, description="Veículos por faixa", examples=[15])
    limite_fluxo_alto: float = Field(gt=0, description="Veículos por faixa", examples=[25])
    verde_minimo_padrao: int = Field(gt=0, le=300, description="Segundos", examples=[15])
    verde_maximo_padrao: int = Field(gt=0, le=300, description="Segundos", examples=[60])
    tempo_maximo_sem_leitura: int = Field(
        ge=30, le=86_400, description="Segundos sem leitura até registrar falha", examples=[300]
    )
    fluxo_saturacao_por_faixa: int = Field(
        ge=600, le=3000, description="Webster: veículos/hora por faixa com verde", examples=[1800]
    )
    intervalo_contagem: int = Field(
        ge=10, le=900, description="Webster: segundos cobertos por cada contagem", examples=[90]
    )
    ciclo_minimo: int = Field(ge=20, le=300, description="Webster: segundos", examples=[40])
    ciclo_maximo: int = Field(ge=30, le=300, description="Webster: segundos", examples=[150])

    @model_validator(mode="after")
    def verificar_consistencia(self) -> "ParametrosUpdate":
        if not self.limite_fluxo_baixo < self.limite_fluxo_moderado < self.limite_fluxo_alto:
            raise ValueError("os limites de fluxo devem ser crescentes: baixo < moderado < alto")
        if self.verde_maximo_padrao < self.verde_minimo_padrao:
            raise ValueError("verdeMaximoPadrao deve ser maior ou igual a verdeMinimoPadrao")
        if self.ciclo_maximo <= self.ciclo_minimo:
            raise ValueError("cicloMaximo deve ser maior que cicloMinimo")
        return self


class ParametrosRead(ParametrosUpdate):
    atualizado_em: datetime
