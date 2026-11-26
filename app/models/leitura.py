from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import UTCDateTime, agora_utc

if TYPE_CHECKING:
    from app.models.via import Via


class LeituraTrafego(Base):
    __tablename__ = "leituras_trafego"
    __table_args__ = (
        CheckConstraint("quantidade_veiculos >= 0", name="ck_leitura_quantidade"),
        # Consulta mais frequente: últimas leituras de uma via (RNF10)
        Index("ix_leituras_via_data_hora", "via_id", "data_hora"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    via_id: Mapped[int] = mapped_column(ForeignKey("vias.id"))
    quantidade_veiculos: Mapped[int] = mapped_column(Integer)
    data_hora: Mapped[datetime] = mapped_column(UTCDateTime(), default=agora_utc)

    via: Mapped["Via"] = relationship(back_populates="leituras")
