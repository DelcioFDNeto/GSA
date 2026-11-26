"""RF07 — classificação do fluxo de cada via em faixas configuráveis."""

from dataclasses import dataclass

from app.motor.modelos import ClassificacaoFluxo


@dataclass(frozen=True)
class FaixasFluxo:
    """Limites superiores, em veículos por faixa de rolamento, de cada classificação.

    Até `baixo` -> BAIXO; até `moderado` -> MODERADO; até `alto` -> ALTO; acima -> CRITICO.
    """

    baixo: float
    moderado: float
    alto: float

    def __post_init__(self) -> None:
        if not 0 < self.baixo < self.moderado < self.alto:
            raise ValueError("faixas de fluxo devem ser positivas e crescentes")

    def classificar(self, quantidade_veiculos: int, quantidade_faixas: int) -> ClassificacaoFluxo:
        veiculos_por_faixa = quantidade_veiculos / quantidade_faixas
        if veiculos_por_faixa <= self.baixo:
            return ClassificacaoFluxo.BAIXO
        if veiculos_por_faixa <= self.moderado:
            return ClassificacaoFluxo.MODERADO
        if veiculos_por_faixa <= self.alto:
            return ClassificacaoFluxo.ALTO
        return ClassificacaoFluxo.CRITICO
