"""Motor de cálculo semafórico — lógica pura, separada da API e do banco (RNF08)."""

from collections.abc import Sequence

from app.motor.classificacao import FaixasFluxo
from app.motor.demanda import calcular_demandas
from app.motor.estagios import Estagio, agrupar_estagios
from app.motor.modelos import (
    AjusteAplicado,
    ClassificacaoFluxo,
    EntradaVia,
    ResultadoCalculo,
    TempoCalculado,
)
from app.motor.regras import DistribuicaoProporcional, PlanoFixo, RegraTemporizacao, Webster

REGRA_PADRAO: RegraTemporizacao = DistribuicaoProporcional()


def calcular_ciclo(
    entradas: Sequence[EntradaVia],
    duracao_ciclo: int,
    faixas: FaixasFluxo,
    regra: RegraTemporizacao = REGRA_PADRAO,
) -> ResultadoCalculo:
    return regra.calcular(entradas, duracao_ciclo, faixas)


__all__ = [
    "AjusteAplicado",
    "ClassificacaoFluxo",
    "DistribuicaoProporcional",
    "EntradaVia",
    "Estagio",
    "FaixasFluxo",
    "PlanoFixo",
    "RegraTemporizacao",
    "ResultadoCalculo",
    "TempoCalculado",
    "Webster",
    "agrupar_estagios",
    "calcular_ciclo",
    "calcular_demandas",
]
