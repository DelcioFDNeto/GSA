from datetime import datetime

from app.models.enums import (
    Direcao,
    ModoOperacao,
    RegraTemporizacao,
    StatusCruzamento,
    StatusSemaforo,
)
from app.motor.modelos import ClassificacaoFluxo
from app.schemas.base import SchemaBase


class UltimaLeitura(SchemaBase):
    quantidade_veiculos: int
    data_hora: datetime


class ViaSituacao(SchemaBase):
    via_id: int
    nome: str
    direcao: Direcao
    quantidade_faixas: int
    estagio: int | None
    semaforo_id: int | None
    status_semaforo: StatusSemaforo | None
    ultima_leitura: UltimaLeitura | None
    leitura_desatualizada: bool
    classificacao_fluxo: ClassificacaoFluxo | None
    tempo_verde_recomendado: int | None


class ResumoCiclo(SchemaBase):
    id: int
    data_hora_inicio: datetime
    origem: str
    duracao_total: int
    total_veiculos: int


class SituacaoRead(SchemaBase):
    """RF14 — fotografia atual do cruzamento."""

    cruzamento_id: int
    nome: str
    status: StatusCruzamento
    regra_temporizacao: RegraTemporizacao
    modo_operacao: ModoOperacao
    consultado_em: datetime
    total_veiculos: int
    ultimo_ciclo: ResumoCiclo | None
    falhas_abertas: int
    vias: list[ViaSituacao]


class EstatisticaVia(SchemaBase):
    via_id: int
    nome: str
    quantidade_leituras: int
    media_veiculos: float | None
    minimo_veiculos: int | None
    maximo_veiculos: int | None
    ultima_leitura_em: datetime | None


class HistoricoRead(SchemaBase):
    """RF15 — resumo do trânsito de um cruzamento em um período."""

    cruzamento_id: int
    inicio: datetime
    fim: datetime
    quantidade_leituras: int
    quantidade_ciclos: int
    duracao_media_ciclo: float | None
    vias: list[EstatisticaVia]
