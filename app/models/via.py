from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import UTCDateTime, agora_utc
from app.models._colunas import coluna_enum
from app.models.enums import Direcao

if TYPE_CHECKING:
    from app.models.cruzamento import Cruzamento
    from app.models.leitura import LeituraTrafego
    from app.models.semaforo import Semaforo


class Via(Base):
    __tablename__ = "vias"
    __table_args__ = (CheckConstraint("quantidade_faixas >= 1", name="ck_via_faixas_positivas"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    direcao: Mapped[Direcao] = mapped_column(coluna_enum(Direcao))
    quantidade_faixas: Mapped[int] = mapped_column(Integer)
    # Vias do mesmo estágio recebem verde juntas; vazio = estágio próprio
    estagio: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cruzamento_id: Mapped[int] = mapped_column(ForeignKey("cruzamentos.id"), index=True)
    # Referência para detectar ausência de leitura quando a via ainda não recebeu nenhuma (RF18)
    criada_em: Mapped[datetime] = mapped_column(UTCDateTime(), default=agora_utc)

    cruzamento: Mapped["Cruzamento"] = relationship(back_populates="vias")
    semaforo: Mapped["Semaforo | None"] = relationship(back_populates="via", uselist=False)
    leituras: Mapped[list["LeituraTrafego"]] = relationship(back_populates="via")
