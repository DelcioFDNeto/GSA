from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._colunas import coluna_enum
from app.models.enums import StatusSemaforo

if TYPE_CHECKING:
    from app.models.via import Via


class Semaforo(Base):
    __tablename__ = "semaforos"
    __table_args__ = (
        CheckConstraint("tempo_minimo_verde > 0", name="ck_semaforo_verde_minimo"),
        CheckConstraint(
            "tempo_maximo_verde >= tempo_minimo_verde", name="ck_semaforo_verde_maximo"
        ),
        CheckConstraint("tempo_amarelo > 0", name="ck_semaforo_amarelo"),
        CheckConstraint("tempo_vermelho >= 0", name="ck_semaforo_vermelho"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Cada via possui no máximo um semáforo (RF02 / RF03)
    via_id: Mapped[int] = mapped_column(ForeignKey("vias.id"), unique=True)
    tempo_minimo_verde: Mapped[int] = mapped_column(Integer)
    tempo_maximo_verde: Mapped[int] = mapped_column(Integer)
    tempo_amarelo: Mapped[int] = mapped_column(Integer)
    # Vermelho de segurança após o amarelo desta via (todas as vias ficam no vermelho)
    tempo_vermelho: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[StatusSemaforo] = mapped_column(
        coluna_enum(StatusSemaforo), default=StatusSemaforo.ATIVO
    )

    via: Mapped["Via"] = relationship(back_populates="semaforo")
