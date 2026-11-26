"""Estruturas de dados do motor de cálculo. Não dependem de FastAPI nem de SQLAlchemy (RNF08)."""

from dataclasses import dataclass
from enum import StrEnum


class ClassificacaoFluxo(StrEnum):
    BAIXO = "baixo"
    MODERADO = "moderado"
    ALTO = "alto"
    CRITICO = "critico"


class AjusteAplicado(StrEnum):
    PROPORCIONAL = "proporcional"
    MINIMO_GARANTIDO = "minimo_garantido"
    MAXIMO_LIMITADO = "maximo_limitado"
    DISTRIBUICAO_IGUAL = "distribuicao_igual"
    PLANO_FIXO = "plano_fixo"  # modo de segurança: divisão fixa, sem usar as contagens


@dataclass(frozen=True)
class EntradaVia:
    via_id: int
    quantidade_veiculos: int
    quantidade_faixas: int
    tempo_minimo_verde: int
    tempo_maximo_verde: int
    tempo_amarelo: int
    tempo_vermelho: int = 0
    # Vias com o mesmo estágio recebem verde ao mesmo tempo (ex.: sentidos opostos da avenida).
    # Sem estágio, a via forma um estágio sozinha.
    estagio: int | None = None

    def __post_init__(self) -> None:
        if self.quantidade_veiculos < 0:
            raise ValueError("quantidade_veiculos não pode ser negativa")
        if self.quantidade_faixas < 1:
            raise ValueError("quantidade_faixas deve ser pelo menos 1")
        if not 0 < self.tempo_minimo_verde <= self.tempo_maximo_verde:
            raise ValueError("tempos de verde inválidos: exige 0 < mínimo <= máximo")
        if self.tempo_amarelo <= 0 or self.tempo_vermelho < 0:
            raise ValueError("tempos de amarelo/vermelho inválidos")


@dataclass(frozen=True)
class TempoCalculado:
    via_id: int
    quantidade_veiculos: int
    demanda: float  # fração de 0 a 1 do total de veículos do cruzamento
    classificacao: ClassificacaoFluxo
    tempo_verde: int
    tempo_amarelo: int
    tempo_vermelho: int  # tempo total em vermelho para esta via dentro do ciclo
    ajuste: AjusteAplicado


@dataclass(frozen=True)
class ResultadoCalculo:
    regra: str
    duracao_ciclo_configurada: int
    verde_disponivel: int
    duracao_total: int
    tempos: list[TempoCalculado]
    grau_saturacao: float | None = None  # soma das razões de fluxo críticas (regra de Webster)
