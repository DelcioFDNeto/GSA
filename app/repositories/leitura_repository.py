from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import LeituraTrafego, Via


class LeituraRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def adicionar_varias(self, leituras: list[LeituraTrafego]) -> list[LeituraTrafego]:
        self.db.add_all(leituras)
        self.db.commit()
        for leitura in leituras:
            self.db.refresh(leitura)
        return leituras

    def listar_por_via(
        self,
        via_id: int,
        inicio: datetime | None = None,
        fim: datetime | None = None,
        limite: int = 100,
    ) -> list[LeituraTrafego]:
        return self._listar([LeituraTrafego.via_id == via_id], inicio, fim, limite)

    def listar_por_cruzamento(
        self,
        cruzamento_id: int,
        inicio: datetime | None = None,
        fim: datetime | None = None,
        limite: int = 100,
        via_id: int | None = None,
    ) -> list[LeituraTrafego]:
        filtros = [
            LeituraTrafego.via_id.in_(select(Via.id).where(Via.cruzamento_id == cruzamento_id))
        ]
        if via_id is not None:
            filtros.append(LeituraTrafego.via_id == via_id)
        return self._listar(filtros, inicio, fim, limite)

    def ultima_da_via(self, via_id: int) -> LeituraTrafego | None:
        leituras = self.listar_por_via(via_id, limite=1)
        return leituras[0] if leituras else None

    def ultimas_por_via(self, via_ids: list[int]) -> dict[int, LeituraTrafego]:
        """Última leitura de cada via em uma única consulta (RNF10).

        A data/hora é atribuída pelo servidor ao gravar, então o maior id é a leitura mais recente.
        """
        if not via_ids:
            return {}
        ultima_id = (
            select(func.max(LeituraTrafego.id).label("id"))
            .where(LeituraTrafego.via_id.in_(via_ids))
            .group_by(LeituraTrafego.via_id)
            .subquery()
        )
        consulta = select(LeituraTrafego).join(ultima_id, LeituraTrafego.id == ultima_id.c.id)
        return {leitura.via_id: leitura for leitura in self.db.scalars(consulta)}

    def estatisticas_por_via(
        self, via_ids: list[int], inicio: datetime, fim: datetime
    ) -> dict[int, tuple[int, float | None, int | None, int | None, datetime | None]]:
        """(quantidade, média, mínimo, máximo, última data) de cada via no período."""
        if not via_ids:
            return {}
        consulta = (
            select(
                LeituraTrafego.via_id,
                func.count(LeituraTrafego.id),
                func.avg(LeituraTrafego.quantidade_veiculos),
                func.min(LeituraTrafego.quantidade_veiculos),
                func.max(LeituraTrafego.quantidade_veiculos),
                func.max(LeituraTrafego.data_hora),
            )
            .where(
                LeituraTrafego.via_id.in_(via_ids),
                LeituraTrafego.data_hora >= inicio,
                LeituraTrafego.data_hora <= fim,
            )
            .group_by(LeituraTrafego.via_id)
        )
        return {linha[0]: tuple(linha[1:]) for linha in self.db.execute(consulta)}

    def _listar(self, filtros, inicio, fim, limite) -> list[LeituraTrafego]:
        consulta = select(LeituraTrafego).where(*filtros)
        if inicio is not None:
            consulta = consulta.where(LeituraTrafego.data_hora >= inicio)
        if fim is not None:
            consulta = consulta.where(LeituraTrafego.data_hora <= fim)
        consulta = consulta.order_by(
            LeituraTrafego.data_hora.desc(), LeituraTrafego.id.desc()
        ).limit(limite)
        return list(self.db.scalars(consulta))
