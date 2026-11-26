from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import CicloSemaforico, TempoSemaforico


class CicloRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def adicionar(self, ciclo: CicloSemaforico) -> CicloSemaforico:
        self.db.add(ciclo)
        self.db.commit()
        return self.obter(ciclo.id)

    def obter(self, ciclo_id: int) -> CicloSemaforico | None:
        consulta = (
            select(CicloSemaforico)
            .where(CicloSemaforico.id == ciclo_id)
            .options(selectinload(CicloSemaforico.tempos).selectinload(TempoSemaforico.via))
        )
        return self.db.scalars(consulta).first()

    def listar(
        self,
        cruzamento_id: int,
        inicio: datetime | None = None,
        fim: datetime | None = None,
        limite: int = 50,
    ) -> list[CicloSemaforico]:
        consulta = (
            select(CicloSemaforico)
            .where(CicloSemaforico.cruzamento_id == cruzamento_id)
            .options(selectinload(CicloSemaforico.tempos).selectinload(TempoSemaforico.via))
        )
        if inicio is not None:
            consulta = consulta.where(CicloSemaforico.data_hora_inicio >= inicio)
        if fim is not None:
            consulta = consulta.where(CicloSemaforico.data_hora_inicio <= fim)
        consulta = consulta.order_by(
            CicloSemaforico.data_hora_inicio.desc(), CicloSemaforico.id.desc()
        ).limit(limite)
        return list(self.db.scalars(consulta))

    def ultimo(self, cruzamento_id: int) -> CicloSemaforico | None:
        ciclos = self.listar(cruzamento_id, limite=1)
        return ciclos[0] if ciclos else None

    def resumo_periodo(
        self, cruzamento_id: int, inicio: datetime, fim: datetime
    ) -> tuple[int, float | None]:
        consulta = select(func.count(CicloSemaforico.id), func.avg(CicloSemaforico.duracao_total))
        consulta = consulta.where(
            CicloSemaforico.cruzamento_id == cruzamento_id,
            CicloSemaforico.data_hora_inicio >= inicio,
            CicloSemaforico.data_hora_inicio <= fim,
        )
        quantidade, media = self.db.execute(consulta).one()
        return quantidade, (float(media) if media is not None else None)
