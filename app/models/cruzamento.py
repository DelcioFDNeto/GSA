from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import UTCDateTime, agora_utc
from app.models._colunas import coluna_enum
from app.models.enums import RegraTemporizacao, StatusCruzamento

if TYPE_CHECKING:
    from app.models.ciclo import CicloSemaforico
    from app.models.via import Via


class Cruzamento(Base):
    __tablename__ = "cruzamentos"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    # Duração do ciclo própria do cruzamento; vazio usa o parâmetro global (RF16)
    duracao_ciclo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    regra_temporizacao: Mapped[RegraTemporizacao] = mapped_column(
        coluna_enum(RegraTemporizacao), default=RegraTemporizacao.PROPORCIONAL
    )
    status: Mapped[StatusCruzamento] = mapped_column(
        coluna_enum(StatusCruzamento), default=StatusCruzamento.ATIVO, index=True
    )
    criado_em: Mapped[datetime] = mapped_column(UTCDateTime(), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=agora_utc, onupdate=agora_utc
    )

    vias: Mapped[list["Via"]] = relationship(back_populates="cruzamento", order_by="Via.id")
    ciclos: Mapped[list["CicloSemaforico"]] = relationship(back_populates="cruzamento")
