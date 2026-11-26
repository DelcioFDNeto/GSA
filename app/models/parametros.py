"""Parâmetros do algoritmo, editáveis pela API (RF16). Há um único registro (id = 1)."""

from datetime import datetime

from sqlalchemy import Float, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UTCDateTime, agora_utc


class ParametrosAlgoritmo(Base):
    __tablename__ = "parametros_algoritmo"

    id: Mapped[int] = mapped_column(primary_key=True)
    duracao_ciclo: Mapped[int] = mapped_column(Integer)
    limite_fluxo_baixo: Mapped[float] = mapped_column(Float)
    limite_fluxo_moderado: Mapped[float] = mapped_column(Float)
    limite_fluxo_alto: Mapped[float] = mapped_column(Float)
    verde_minimo_padrao: Mapped[int] = mapped_column(Integer)
    verde_maximo_padrao: Mapped[int] = mapped_column(Integer)
    tempo_maximo_sem_leitura: Mapped[int] = mapped_column(Integer)
    # Regra de Webster
    fluxo_saturacao_por_faixa: Mapped[int] = mapped_column(Integer)
    intervalo_contagem: Mapped[int] = mapped_column(Integer)
    ciclo_minimo: Mapped[int] = mapped_column(Integer)
    ciclo_maximo: Mapped[int] = mapped_column(Integer)
    atualizado_em: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=agora_utc, onupdate=agora_utc
    )
