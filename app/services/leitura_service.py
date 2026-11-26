from datetime import datetime

from sqlalchemy.orm import Session

from app.core.eventos import canal
from app.core.exceptions import RecursoNaoEncontrado, RegraDeNegocioViolada
from app.db.types import agora_utc
from app.models import Cruzamento, LeituraTrafego, OrigemCiclo, StatusCruzamento, TipoFalha
from app.repositories.leitura_repository import LeituraRepository
from app.repositories.via_repository import ViaRepository
from app.schemas.ciclo import CicloGeradoRead
from app.schemas.leitura import LeituraLoteCreate
from app.services.ciclo_service import CicloService
from app.services.cruzamento_service import CruzamentoService
from app.services.falha_service import FalhaService
from app.services.via_service import ViaService


def _exigir_ativo(cruzamento: Cruzamento) -> None:
    if cruzamento.status != StatusCruzamento.ATIVO:
        raise RegraDeNegocioViolada(
            f"Cruzamento {cruzamento.id} está inativo e não aceita novas leituras"
        )


class LeituraService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = LeituraRepository(db)
        self.vias_repo = ViaRepository(db)
        self.vias = ViaService(db)
        self.cruzamentos = CruzamentoService(db)
        self.falhas = FalhaService(db)

    def registrar_lote(
        self, cruzamento_id: int, dados: LeituraLoteCreate, momento: datetime | None = None
    ) -> tuple[list[LeituraTrafego], CicloGeradoRead | None, list[str]]:
        """RF04/RF05/RF12 — valida o lote inteiro (tudo ou nada), grava as leituras e gera
        um novo ciclo semafórico a partir delas."""
        if dados.cruzamento_id != cruzamento_id:
            raise RegraDeNegocioViolada(
                f"cruzamentoId do corpo ({dados.cruzamento_id}) difere do da URL ({cruzamento_id})"
            )
        _exigir_ativo(self.cruzamentos.obter(cruzamento_id))

        ids = [item.via_id for item in dados.leituras]
        vias = self.vias_repo.obter_varias(ids)
        for via_id in ids:
            if via_id not in vias:
                raise RecursoNaoEncontrado("Via", via_id)
        de_outro_cruzamento = [v for v in ids if vias[v].cruzamento_id != cruzamento_id]
        if de_outro_cruzamento:
            raise RegraDeNegocioViolada(
                f"Vias {de_outro_cruzamento} não pertencem ao cruzamento {cruzamento_id}"
            )

        momento = momento or agora_utc()
        leituras = self.repo.adicionar_varias(
            [
                LeituraTrafego(
                    via_id=item.via_id,
                    quantidade_veiculos=item.quantidade_veiculos,
                    data_hora=momento,
                )
                for item in dados.leituras
            ]
        )
        self.falhas.resolver_sem_leitura(ids, momento)
        _publicar_leituras(cruzamento_id, leituras)

        avisos: list[str] = []
        try:
            ciclo = CicloService(self.db).gerar(
                cruzamento_id, OrigemCiclo.AUTOMATICO, momento=momento
            )
        except RegraDeNegocioViolada as erro:
            ciclo = None
            avisos.append(f"Leituras gravadas, mas o ciclo não foi gerado: {erro.mensagem}")
            self.falhas.registrar_automatica(
                cruzamento_id, TipoFalha.CALCULO_INDISPONIVEL, erro.mensagem
            )
        else:
            self.falhas.resolver_automatica(
                cruzamento_id, TipoFalha.CALCULO_INDISPONIVEL, "Ciclo gerado com sucesso"
            )
        return leituras, ciclo, avisos

    def registrar_por_via(self, via_id: int, quantidade_veiculos: int) -> LeituraTrafego:
        """Leitura avulsa de uma via. Não gera ciclo: o fluxo do detector é o envio em lote."""
        via = self.vias.obter(via_id)
        _exigir_ativo(via.cruzamento)
        momento = agora_utc()
        leitura = LeituraTrafego(
            via_id=via_id, quantidade_veiculos=quantidade_veiculos, data_hora=momento
        )
        leitura = self.repo.adicionar_varias([leitura])[0]
        self.falhas.resolver_sem_leitura([via_id], momento)
        _publicar_leituras(via.cruzamento_id, [leitura])
        return leitura

    def listar_por_via(
        self,
        via_id: int,
        inicio: datetime | None,
        fim: datetime | None,
        limite: int,
    ) -> list[LeituraTrafego]:
        self.vias.obter(via_id)
        _validar_periodo(inicio, fim)
        return self.repo.listar_por_via(via_id, inicio, fim, limite)

    def listar_por_cruzamento(
        self,
        cruzamento_id: int,
        inicio: datetime | None,
        fim: datetime | None,
        via_id: int | None,
        limite: int,
    ) -> list[LeituraTrafego]:
        """RF15 — histórico de leituras de todas as vias (ou de uma via) do cruzamento."""
        self.cruzamentos.obter(cruzamento_id)
        _validar_periodo(inicio, fim)
        if via_id is not None and self.vias.obter(via_id).cruzamento_id != cruzamento_id:
            raise RegraDeNegocioViolada(f"Via {via_id} não pertence ao cruzamento {cruzamento_id}")
        return self.repo.listar_por_cruzamento(cruzamento_id, inicio, fim, limite, via_id)


def _publicar_leituras(cruzamento_id: int, leituras: list[LeituraTrafego]) -> None:
    canal.publicar(
        "leituras",
        {
            "cruzamentoId": cruzamento_id,
            "leituras": [
                {
                    "viaId": leitura.via_id,
                    "quantidadeVeiculos": leitura.quantidade_veiculos,
                    "dataHora": leitura.data_hora.isoformat(),
                }
                for leitura in leituras
            ],
        },
    )


def _validar_periodo(inicio: datetime | None, fim: datetime | None) -> None:
    if inicio and fim and inicio > fim:
        raise RegraDeNegocioViolada("O parâmetro 'inicio' deve ser anterior a 'fim'")
