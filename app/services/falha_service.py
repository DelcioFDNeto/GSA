"""RF18 — registro de falhas e situações anormais.

A ausência prolongada de leitura é verificada periodicamente (tarefa em segundo plano iniciada
com a API) ou sob demanda (POST /falhas/verificar). Uma nova leitura da via resolve a falha.
"""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.eventos import canal
from app.core.exceptions import RecursoNaoEncontrado, RegraDeNegocioViolada
from app.db.types import agora_utc
from app.models import Falha, StatusFalha, TipoFalha
from app.repositories.falha_repository import FalhaRepository
from app.repositories.leitura_repository import LeituraRepository
from app.repositories.via_repository import ViaRepository
from app.schemas.falha import FalhaCreate, FalhaRead
from app.services.cruzamento_service import CruzamentoService
from app.services.parametro_service import ParametroService


class FalhaService:
    def __init__(self, db: Session) -> None:
        self.repo = FalhaRepository(db)
        self.vias = ViaRepository(db)
        self.leituras = LeituraRepository(db)
        self.parametros = ParametroService(db)
        self.cruzamentos = CruzamentoService(db)

    def verificar_ausencia_leituras(self, agora: datetime | None = None) -> list[Falha]:
        agora = agora or agora_utc()
        limite = timedelta(seconds=self.parametros.obter().tempo_maximo_sem_leitura)
        vias = self.vias.listar_monitoradas()
        ids = [via.id for via in vias]
        ultimas = self.leituras.ultimas_por_via(ids)
        ja_abertas = {falha.via_id for falha in self.repo.abertas_sem_leitura(ids)}

        novas = []
        for via in vias:
            ultima = ultimas.get(via.id)
            referencia = ultima.data_hora if ultima else via.criada_em
            if via.id in ja_abertas or agora - referencia <= limite:
                continue
            desde = (
                f"desde {referencia:%d/%m/%Y %H:%M} UTC" if ultima else "desde o cadastro da via"
            )
            falha = Falha(
                cruzamento_id=via.cruzamento_id,
                via_id=via.id,
                tipo=TipoFalha.SEM_LEITURA,
                descricao=(
                    f"Via '{via.nome}' sem leitura {desde} "
                    f"(limite de {int(limite.total_seconds())} s)"
                ),
                detectada_em=agora,
            )
            novas.append(self.repo.adicionar(falha))
        for falha in novas:
            _publicar(falha)
        return novas

    def resolver_sem_leitura(self, via_ids: list[int], momento: datetime | None = None) -> int:
        """Chamado quando chegam leituras: encerra as falhas de ausência dessas vias."""
        falhas = self.repo.abertas_sem_leitura(via_ids)
        for falha in falhas:
            self._marcar_resolvida(falha, "Leitura recebida", momento)
        if falhas:
            self.repo.salvar()
            for falha in falhas:
                _publicar(falha)
        return len(falhas)

    def registrar_automatica(
        self, cruzamento_id: int, tipo: TipoFalha, descricao: str
    ) -> Falha | None:
        """Registra a falha apenas se não houver outra aberta do mesmo tipo no cruzamento."""
        if self.repo.abertas(cruzamento_id, tipo):
            return None
        falha = self.repo.adicionar(
            Falha(cruzamento_id=cruzamento_id, tipo=tipo, descricao=descricao[:300])
        )
        _publicar(falha)
        return falha

    def resolver_automatica(self, cruzamento_id: int, tipo: TipoFalha, observacao: str) -> None:
        falhas = self.repo.abertas(cruzamento_id, tipo)
        for falha in falhas:
            self._marcar_resolvida(falha, observacao)
        if falhas:
            self.repo.salvar()
            for falha in falhas:
                _publicar(falha)

    def registrar_manual(self, cruzamento_id: int, dados: FalhaCreate) -> Falha:
        self.cruzamentos.obter(cruzamento_id)
        if dados.via_id is not None:
            via = self.vias.obter(dados.via_id)
            if via is None:
                raise RecursoNaoEncontrado("Via", dados.via_id)
            if via.cruzamento_id != cruzamento_id:
                raise RegraDeNegocioViolada(
                    f"Via {dados.via_id} não pertence ao cruzamento {cruzamento_id}"
                )
        falha = self.repo.adicionar(
            Falha(
                cruzamento_id=cruzamento_id,
                via_id=dados.via_id,
                tipo=TipoFalha.MANUAL,
                descricao=dados.descricao,
            )
        )
        _publicar(falha)
        return falha

    def resolver(self, falha_id: int, observacao: str | None) -> Falha:
        falha = self.obter(falha_id)
        if falha.status == StatusFalha.RESOLVIDA:
            raise RegraDeNegocioViolada(f"Falha {falha_id} já está resolvida")
        self._marcar_resolvida(falha, observacao)
        self.repo.salvar()
        _publicar(falha)
        return falha

    def obter(self, falha_id: int) -> Falha:
        falha = self.repo.obter(falha_id)
        if falha is None:
            raise RecursoNaoEncontrado("Falha", falha_id)
        return falha

    def listar(
        self,
        cruzamento_id: int | None,
        status: StatusFalha | None,
        tipo: TipoFalha | None,
        limite: int,
    ) -> list[Falha]:
        if cruzamento_id is not None:
            self.cruzamentos.obter(cruzamento_id)
        return self.repo.listar(cruzamento_id, status, tipo, limite)

    @staticmethod
    def _marcar_resolvida(
        falha: Falha, observacao: str | None, momento: datetime | None = None
    ) -> None:
        falha.status = StatusFalha.RESOLVIDA
        falha.resolvida_em = momento or agora_utc()
        falha.observacao_resolucao = observacao


def _publicar(falha: Falha) -> None:
    canal.publicar("falha", FalhaRead.model_validate(falha).model_dump(mode="json", by_alias=True))
