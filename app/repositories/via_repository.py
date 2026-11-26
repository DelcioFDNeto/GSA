from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Cruzamento, Semaforo, StatusCruzamento, StatusSemaforo, Via


class ViaRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def adicionar(self, via: Via) -> Via:
        self.db.add(via)
        self.db.commit()
        self.db.refresh(via)
        return via

    def salvar(self, via: Via) -> Via:
        self.db.commit()
        self.db.refresh(via)
        return via

    def obter(self, via_id: int) -> Via | None:
        return self.db.get(Via, via_id)

    def obter_varias(self, ids: list[int]) -> dict[int, Via]:
        vias = self.db.scalars(select(Via).where(Via.id.in_(ids)))
        return {via.id: via for via in vias}

    def listar_por_cruzamento(self, cruzamento_id: int) -> list[Via]:
        consulta = (
            select(Via)
            .where(Via.cruzamento_id == cruzamento_id)
            .options(selectinload(Via.semaforo))
            .order_by(Via.id)
        )
        return list(self.db.scalars(consulta))

    def listar_monitoradas(self) -> list[Via]:
        """Vias de cruzamentos ativos com semáforo ativo — as que devem enviar leituras."""
        consulta = (
            select(Via)
            .join(Cruzamento, Via.cruzamento_id == Cruzamento.id)
            .join(Semaforo, Semaforo.via_id == Via.id)
            .where(
                Cruzamento.status == StatusCruzamento.ATIVO,
                Semaforo.status == StatusSemaforo.ATIVO,
            )
            .order_by(Via.id)
        )
        return list(self.db.scalars(consulta))


class SemaforoRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def adicionar(self, semaforo: Semaforo) -> Semaforo:
        self.db.add(semaforo)
        self.db.commit()
        self.db.refresh(semaforo)
        return semaforo

    def salvar(self, semaforo: Semaforo) -> Semaforo:
        self.db.commit()
        self.db.refresh(semaforo)
        return semaforo

    def obter(self, semaforo_id: int) -> Semaforo | None:
        return self.db.get(Semaforo, semaforo_id)

    def obter_por_via(self, via_id: int) -> Semaforo | None:
        return self.db.scalars(select(Semaforo).where(Semaforo.via_id == via_id)).first()

    def listar_por_cruzamento(self, cruzamento_id: int) -> list[Semaforo]:
        consulta = (
            select(Semaforo)
            .join(Via, Semaforo.via_id == Via.id)
            .where(Via.cruzamento_id == cruzamento_id)
            .order_by(Semaforo.id)
        )
        return list(self.db.scalars(consulta))
