"""Ciclos semafóricos calculados e o tempo de cada semáforo no ciclo (RF12/RF13)."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import UTCDateTime, agora_utc
from app.models._colunas import coluna_enum
from app.models.enums import ModoOperacao, OrigemCiclo

if TYPE_CHECKING:
    from app.models.cruzamento import Cruzamento
    from app.models.semaforo import Semaforo
    from app.models.via import Via


class CicloSemaforico(Base):
    __tablename__ = "ciclos_semaforicos"
    __table_args__ = (Index("ix_ciclos_cruzamento_data", "cruzamento_id", "data_hora_inicio"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    cruzamento_id: Mapped[int] = mapped_column(ForeignKey("cruzamentos.id"), index=True)
    data_hora_inicio: Mapped[datetime] = mapped_column(UTCDateTime(), default=agora_utc)
    origem: Mapped[OrigemCiclo] = mapped_column(coluna_enum(OrigemCiclo))
    modo_operacao: Mapped[ModoOperacao] = mapped_column(
        coluna_enum(ModoOperacao), default=ModoOperacao.ADAPTATIVO
    )
    regra_aplicada: Mapped[str] = mapped_column(String(60))
    duracao_ciclo_configurada: Mapped[int] = mapped_column(Integer)
    verde_disponivel: Mapped[int] = mapped_column(Integer)
    duracao_total: Mapped[int] = mapped_column(Integer)
    total_veiculos: Mapped[int] = mapped_column(Integer)
    grau_saturacao: Mapped[float | None] = mapped_column(Float, nullable=True)  # Webster

    cruzamento: Mapped["Cruzamento"] = relationship(back_populates="ciclos")
    tempos: Mapped[list["TempoSemaforico"]] = relationship(
        back_populates="ciclo", cascade="all, delete-orphan", order_by="TempoSemaforico.id"
    )


class TempoSemaforico(Base):
    __tablename__ = "tempos_semaforicos"

    id: Mapped[int] = mapped_column(primary_key=True)
    ciclo_id: Mapped[int] = mapped_column(ForeignKey("ciclos_semaforicos.id"), index=True)
    semaforo_id: Mapped[int] = mapped_column(ForeignKey("semaforos.id"))
    via_id: Mapped[int] = mapped_column(
        ForeignKey("vias.id", name="fk_tempos_semaforicos_via_id_vias")
    )
    quantidade_veiculos: Mapped[int] = mapped_column(Integer)
    demanda_percentual: Mapped[float] = mapped_column(Float)
    classificacao_fluxo: Mapped[str] = mapped_column(String(20))
    tempo_verde: Mapped[int] = mapped_column(Integer)
    tempo_amarelo: Mapped[int] = mapped_column(Integer)
    tempo_vermelho: Mapped[int] = mapped_column(Integer)
    ajuste_aplicado: Mapped[str] = mapped_column(String(30))

    ciclo: Mapped["CicloSemaforico"] = relationship(back_populates="tempos")
    semaforo: Mapped["Semaforo"] = relationship()
    via: Mapped["Via"] = relationship()
