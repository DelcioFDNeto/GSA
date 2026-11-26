from sqlalchemy.orm import Session

from app.core.exceptions import RecursoNaoEncontrado
from app.models import Cruzamento, StatusCruzamento
from app.repositories.cruzamento_repository import CruzamentoRepository
from app.schemas.cruzamento import CruzamentoCreate, CruzamentoUpdate


class CruzamentoService:
    def __init__(self, db: Session) -> None:
        self.repo = CruzamentoRepository(db)

    def criar(self, dados: CruzamentoCreate) -> Cruzamento:
        return self.repo.adicionar(Cruzamento(**dados.model_dump()))

    def listar(self, status: StatusCruzamento | None = None) -> list[Cruzamento]:
        return self.repo.listar(status)

    def obter(self, cruzamento_id: int) -> Cruzamento:
        cruzamento = self.repo.obter(cruzamento_id)
        if cruzamento is None:
            raise RecursoNaoEncontrado("Cruzamento", cruzamento_id)
        return cruzamento

    def obter_detalhe(self, cruzamento_id: int) -> Cruzamento:
        cruzamento = self.repo.obter_com_vias(cruzamento_id)
        if cruzamento is None:
            raise RecursoNaoEncontrado("Cruzamento", cruzamento_id)
        return cruzamento

    def atualizar(self, cruzamento_id: int, dados: CruzamentoUpdate) -> Cruzamento:
        cruzamento = self.obter(cruzamento_id)
        for campo, valor in dados.model_dump().items():
            setattr(cruzamento, campo, valor)
        return self.repo.salvar(cruzamento)

    def ativar(self, cruzamento_id: int) -> Cruzamento:
        """RF17 — reativa o cruzamento, que volta a aceitar leituras e gerar ciclos."""
        cruzamento = self.obter(cruzamento_id)
        cruzamento.status = StatusCruzamento.ATIVO
        return self.repo.salvar(cruzamento)

    def desativar(self, cruzamento_id: int) -> Cruzamento:
        """RF17 — exclusão lógica: o cruzamento fica inativo e o histórico é preservado."""
        cruzamento = self.obter(cruzamento_id)
        cruzamento.status = StatusCruzamento.INATIVO
        return self.repo.salvar(cruzamento)
