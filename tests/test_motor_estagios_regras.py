"""Estágios (vias que abrem juntas), plano fixo do modo de segurança e regra de Webster."""

import pytest

from app.motor import (
    AjusteAplicado,
    EntradaVia,
    FaixasFluxo,
    PlanoFixo,
    Webster,
    calcular_ciclo,
)

FAIXAS = FaixasFluxo(baixo=5, moderado=15, alto=25)


def via(via_id, veiculos, estagio=None, faixas=1, minimo=20, maximo=70, amarelo=3, vermelho=2):
    return EntradaVia(via_id, veiculos, faixas, minimo, maximo, amarelo, vermelho, estagio)


def verdes(resultado):
    return {t.via_id: t.tempo_verde for t in resultado.tempos}


def test_vias_do_mesmo_estagio_recebem_o_mesmo_verde():
    # Estágio 1: sentidos norte (30) e sul (10); estágio 2: leste (20).
    entradas = [via(1, 30, estagio=1), via(2, 10, estagio=1), via(3, 20, estagio=2)]
    resultado = calcular_ciclo(entradas, 90, FAIXAS)

    # Dois entreverdes de 5 s: 80 s de verde, divididos 30:20 (via mais carregada de cada estágio)
    assert resultado.verde_disponivel == 80
    assert verdes(resultado) == {1: 48, 2: 48, 3: 32}
    assert resultado.duracao_total == 90


def test_estagio_respeita_os_limites_mais_restritivos_das_vias():
    entradas = [
        via(1, 100, estagio=1, minimo=20, maximo=70),
        via(2, 100, estagio=1, minimo=25, maximo=50),
        via(3, 1, estagio=2, minimo=10, maximo=60),
    ]
    tempos = {t.via_id: t for t in calcular_ciclo(entradas, 90, FAIXAS).tempos}
    assert tempos[1].tempo_verde == tempos[2].tempo_verde == 50  # menor máximo do estágio
    assert tempos[1].ajuste == AjusteAplicado.MAXIMO_LIMITADO


def test_plano_fixo_ignora_as_contagens():
    resultado = calcular_ciclo([via(1, 30), via(2, 10)], 90, FAIXAS, regra=PlanoFixo())
    assert resultado.regra == "plano_fixo"
    assert verdes(resultado) == {1: 40, 2: 40}
    assert all(t.ajuste == AjusteAplicado.PLANO_FIXO for t in resultado.tempos)


def test_webster_aplica_a_formula_do_ciclo_otimo():
    # 18 e 9 veículos em 90 s -> 720 e 360 veíc/h; saturação 1800 veíc/h por faixa
    # y = 0,4 e 0,2 -> Y = 0,6; L = 10 s -> C = (1,5·10 + 5) / (1 − 0,6) = 50 s
    entradas = [via(1, 18, minimo=5), via(2, 9, minimo=5)]
    resultado = calcular_ciclo(entradas, 90, FAIXAS, regra=Webster())

    assert resultado.regra == "webster"
    assert resultado.grau_saturacao == pytest.approx(0.6)
    assert resultado.duracao_ciclo_configurada == 50
    assert verdes(resultado) == {1: 27, 2: 13}  # 40 s de verde na razão 2:1
    assert resultado.duracao_total == 50


def test_webster_considera_o_numero_de_faixas():
    # Mesmos 20 veículos: a via com 2 faixas tem metade da razão de fluxo
    entradas = [via(1, 20, faixas=2, minimo=5), via(2, 20, faixas=1, minimo=5)]
    tempos = verdes(calcular_ciclo(entradas, 90, FAIXAS, regra=Webster()))
    assert tempos[2] == pytest.approx(2 * tempos[1], abs=1)


def test_webster_ajusta_o_ciclo_a_demanda():
    regra = Webster(ciclo_minimo=40, ciclo_maximo=150)
    vazio = calcular_ciclo([via(1, 0), via(2, 0)], 90, FAIXAS, regra=regra)
    moderado = calcular_ciclo([via(1, 20), via(2, 10)], 90, FAIXAS, regra=regra)
    saturado = calcular_ciclo([via(1, 30), via(2, 30)], 90, FAIXAS, regra=regra)

    assert vazio.duracao_ciclo_configurada == 40
    assert 40 < moderado.duracao_ciclo_configurada < 150
    assert saturado.duracao_ciclo_configurada == 150


@pytest.mark.parametrize(
    "parametros",
    [
        {"fluxo_saturacao_por_faixa": 0},
        {"intervalo_contagem": 0},
        {"ciclo_minimo": 100, "ciclo_maximo": 90},
        {"limite_saturacao": 1.2},
    ],
)
def test_webster_rejeita_parametros_invalidos(parametros):
    with pytest.raises(ValueError):
        Webster(**parametros)
