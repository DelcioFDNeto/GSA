from sqlalchemy.orm import Session

from app.core.exceptions import RecursoNaoEncontrado, RegraDeNegocioViolada
from app.models import Semaforo, Via
from app.repositories.via_repository import SemaforoRepository, ViaRepository
from app.schemas.semaforo import SemaforoCreate, SemaforoUpdate
from app.schemas.via import ViaCreate, ViaUpdate
from app.services.cruzamento_service import CruzamentoService
from app.services.parametro_service import ParametroService


class ViaService:
    def __init__(self, db: Session) -> None:
        self.repo = ViaRepository(db)
        self.cruzamentos = CruzamentoService(db)

    def criar(self, cruzamento_id: int, dados: ViaCreate) -> Via:
        self.cruzamentos.obter(cruzamento_id)
        return self.repo.adicionar(Via(cruzamento_id=cruzamento_id, **dados.model_dump()))

    def listar_por_cruzamento(self, cruzamento_id: int) -> list[Via]:
        self.cruzamentos.obter(cruzamento_id)
        return self.repo.listar_por_cruzamento(cruzamento_id)

    def obter(self, via_id: int) -> Via:
        via = self.repo.obter(via_id)
        if via is None:
            raise RecursoNaoEncontrado("Via", via_id)
        return via

    def atualizar(self, via_id: int, dados: ViaUpdate) -> Via:
        via = self.obter(via_id)
        for campo, valor in dados.model_dump().items():
            setattr(via, campo, valor)
        return self.repo.salvar(via)


class SemaforoService:
    def __init__(self, db: Session) -> None:
        self.repo = SemaforoRepository(db)
        self.vias = ViaService(db)

    def criar(self, via_id: int, dados: SemaforoCreate) -> Semaforo:
        self.vias.obter(via_id)
        if self.repo.obter_por_via(via_id) is not None:
            raise RegraDeNegocioViolada(f"A via {via_id} já possui semáforo cadastrado")
        valores = dados.model_dump()
        parametros = ParametroService(self.repo.db).obter()
        valores["tempo_minimo_verde"] = (
            valores["tempo_minimo_verde"] or parametros.verde_minimo_padrao
        )
        valores["tempo_maximo_verde"] = (
            valores["tempo_maximo_verde"] or parametros.verde_maximo_padrao
        )
        if valores["tempo_maximo_verde"] < valores["tempo_minimo_verde"]:
            raise RegraDeNegocioViolada(
                "tempoMaximoVerde ficou menor que tempoMinimoVerde; informe os dois valores"
            )
        return self.repo.adicionar(Semaforo(via_id=via_id, **valores))

    def obter(self, semaforo_id: int) -> Semaforo:
        semaforo = self.repo.obter(semaforo_id)
        if semaforo is None:
            raise RecursoNaoEncontrado("Semáforo", semaforo_id)
        return semaforo

    def obter_por_via(self, via_id: int) -> Semaforo:
        self.vias.obter(via_id)
        semaforo = self.repo.obter_por_via(via_id)
        if semaforo is None:
            raise RegraDeNegocioViolada(f"A via {via_id} ainda não possui semáforo cadastrado")
        return semaforo

    def listar_por_cruzamento(self, cruzamento_id: int) -> list[Semaforo]:
        self.vias.cruzamentos.obter(cruzamento_id)
        return self.repo.listar_por_cruzamento(cruzamento_id)

    def atualizar(self, semaforo_id: int, dados: SemaforoUpdate) -> Semaforo:
        semaforo = self.obter(semaforo_id)
        for campo, valor in dados.model_dump().items():
            setattr(semaforo, campo, valor)
        return self.repo.salvar(semaforo)
