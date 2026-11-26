"""Falhas e situações anormais (RF18)."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import UTCDateTime, agora_utc
from app.models._colunas import coluna_enum
from app.models.enums import StatusFalha, TipoFalha

if TYPE_CHECKING:
    from app.models.cruzamento import Cruzamento
    from app.models.via import Via


class Falha(Base):
    __tablename__ = "falhas"
    __table_args__ = (Index("ix_falhas_cruzamento_status", "cruzamento_id", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    cruzamento_id: Mapped[int] = mapped_column(ForeignKey("cruzamentos.id"))
    via_id: Mapped[int | None] = mapped_column(ForeignKey("vias.id"), nullable=True)
    tipo: Mapped[TipoFalha] = mapped_column(coluna_enum(TipoFalha))
    status: Mapped[StatusFalha] = mapped_column(
        coluna_enum(StatusFalha), default=StatusFalha.ABERTA
    )
    descricao: Mapped[str] = mapped_column(String(300))
    detectada_em: Mapped[datetime] = mapped_column(UTCDateTime(), default=agora_utc)
    resolvida_em: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    observacao_resolucao: Mapped[str | None] = mapped_column(String(300), nullable=True)

    cruzamento: Mapped["Cruzamento"] = relationship()
    via: Mapped["Via | None"] = relationship()
