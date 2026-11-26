from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Cruzamento, StatusCruzamento, Via


class CruzamentoRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def adicionar(self, cruzamento: Cruzamento) -> Cruzamento:
        self.db.add(cruzamento)
        self.db.commit()
        self.db.refresh(cruzamento)
        return cruzamento

    def salvar(self, cruzamento: Cruzamento) -> Cruzamento:
        self.db.commit()
        self.db.refresh(cruzamento)
        return cruzamento

    def obter(self, cruzamento_id: int) -> Cruzamento | None:
        return self.db.get(Cruzamento, cruzamento_id)

    def obter_com_vias(self, cruzamento_id: int) -> Cruzamento | None:
        consulta = (
            select(Cruzamento)
            .where(Cruzamento.id == cruzamento_id)
            .options(selectinload(Cruzamento.vias).selectinload(Via.semaforo))
        )
        return self.db.scalars(consulta).first()

    def listar(self, status: StatusCruzamento | None = None) -> list[Cruzamento]:
        consulta = select(Cruzamento).order_by(Cruzamento.id)
        if status is not None:
            consulta = consulta.where(Cruzamento.status == status)
        return list(self.db.scalars(consulta))
