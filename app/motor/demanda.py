"""RF06 — demanda de cada via como fração do total de veículos do cruzamento."""

from collections.abc import Sequence

from app.motor.modelos import EntradaVia


def calcular_demandas(entradas: Sequence[EntradaVia]) -> dict[int, float]:
    total = sum(e.quantidade_veiculos for e in entradas)
    if total == 0:
        return {e.via_id: 0.0 for e in entradas}
    return {e.via_id: e.quantidade_veiculos / total for e in entradas}
