from datetime import datetime

from app.models.enums import ModoOperacao, OrigemCiclo
from app.motor.modelos import AjusteAplicado, ClassificacaoFluxo
from app.schemas.base import SchemaBase


class TempoRead(SchemaBase):
    via_id: int
    nome_via: str
    semaforo_id: int
    quantidade_veiculos: int
    demanda_percentual: float
    classificacao_fluxo: ClassificacaoFluxo
    tempo_verde: int
    tempo_amarelo: int
    tempo_vermelho: int
    ajuste_aplicado: AjusteAplicado


class ViaIgnorada(SchemaBase):
    via_id: int
    motivo: str


class CicloRead(SchemaBase):
    id: int | None
    cruzamento_id: int
    data_hora_inicio: datetime
    origem: OrigemCiclo
    modo_operacao: ModoOperacao
    regra_aplicada: str
    duracao_ciclo_configurada: int
    verde_disponivel: int
    duracao_total: int
    total_veiculos: int
    grau_saturacao: float | None
    persistido: bool
    tempos: list[TempoRead]


class CicloGeradoRead(CicloRead):
    vias_ignoradas: list[ViaIgnorada]
    motivo_contingencia: str | None = None
