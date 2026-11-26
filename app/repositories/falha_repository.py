from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Falha, StatusFalha, TipoFalha


class FalhaRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def adicionar(self, falha: Falha) -> Falha:
        self.db.add(falha)
        self.db.commit()
        self.db.refresh(falha)
        return falha

    def salvar(self) -> None:
        self.db.commit()

    def obter(self, falha_id: int) -> Falha | None:
        return self.db.get(Falha, falha_id)

    def listar(
        self,
        cruzamento_id: int | None = None,
        status: StatusFalha | None = None,
        tipo: TipoFalha | None = None,
        limite: int = 100,
    ) -> list[Falha]:
        consulta = select(Falha)
        if cruzamento_id is not None:
            consulta = consulta.where(Falha.cruzamento_id == cruzamento_id)
        if status is not None:
            consulta = consulta.where(Falha.status == status)
        if tipo is not None:
            consulta = consulta.where(Falha.tipo == tipo)
        consulta = consulta.order_by(Falha.detectada_em.desc(), Falha.id.desc()).limit(limite)
        return list(self.db.scalars(consulta))

    def abertas(
        self, cruzamento_id: int, tipo: TipoFalha, via_id: int | None = None
    ) -> list[Falha]:
        consulta = select(Falha).where(
            Falha.cruzamento_id == cruzamento_id,
            Falha.tipo == tipo,
            Falha.status == StatusFalha.ABERTA,
        )
        if via_id is not None:
            consulta = consulta.where(Falha.via_id == via_id)
        return list(self.db.scalars(consulta))

    def abertas_sem_leitura(self, via_ids: list[int]) -> list[Falha]:
        if not via_ids:
            return []
        consulta = select(Falha).where(
            Falha.via_id.in_(via_ids),
            Falha.tipo == TipoFalha.SEM_LEITURA,
            Falha.status == StatusFalha.ABERTA,
        )
        return list(self.db.scalars(consulta))

    def contar_abertas(self, cruzamento_id: int) -> int:
        consulta = select(func.count(Falha.id)).where(
            Falha.cruzamento_id == cruzamento_id, Falha.status == StatusFalha.ABERTA
        )
        return self.db.scalar(consulta) or 0
