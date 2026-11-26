"""Testes unitários do motor de cálculo (RF06–RF11)."""

import pytest

from app.motor import (
    AjusteAplicado,
    ClassificacaoFluxo,
    EntradaVia,
    FaixasFluxo,
    calcular_ciclo,
    calcular_demandas,
)

FAIXAS = FaixasFluxo(baixo=5, moderado=15, alto=25)


def via(via_id, veiculos, faixas=1, minimo=20, maximo=70, amarelo=3, vermelho=2):
    return EntradaVia(via_id, veiculos, faixas, minimo, maximo, amarelo, vermelho)


def por_via(resultado):
    return {t.via_id: t for t in resultado.tempos}


def test_exemplo_do_documento_de_requisitos():
    # 80 s de verde disponível (90 s de ciclo - 2 x (3 s amarelo + 2 s vermelho)), 30 e 10 veículos
    resultado = calcular_ciclo([via(1, 30), via(2, 10)], duracao_ciclo=90, faixas=FAIXAS)
    tempos = por_via(resultado)

    assert resultado.verde_disponivel == 80
    assert tempos[1].demanda == pytest.approx(0.75)
    assert tempos[2].demanda == pytest.approx(0.25)
    assert tempos[1].tempo_verde == 60
    assert tempos[2].tempo_verde == 20
    assert resultado.duracao_total == 90


def test_demanda_proporcional_ao_total_de_veiculos():
    demandas = calcular_demandas([via(1, 6), via(2, 3), via(3, 1)])
    assert demandas == pytest.approx({1: 0.6, 2: 0.3, 3: 0.1})


def test_demanda_zero_quando_nao_ha_veiculos():
    assert calcular_demandas([via(1, 0), via(2, 0)]) == {1: 0.0, 2: 0.0}


def test_garante_verde_minimo_e_redistribui_o_restante():
    # Proporção pura daria 76 s e 4 s; a via B sobe para o mínimo e A recebe o que sobra
    tempos = por_via(calcular_ciclo([via(1, 38, maximo=80), via(2, 2)], 90, FAIXAS))

    assert tempos[2].tempo_verde == 20
    assert tempos[2].ajuste == AjusteAplicado.MINIMO_GARANTIDO
    assert tempos[1].tempo_verde == 60
    assert tempos[1].ajuste == AjusteAplicado.PROPORCIONAL


def test_limita_ao_verde_maximo():
    tempos = por_via(calcular_ciclo([via(1, 50, maximo=45), via(2, 10, minimo=10)], 90, FAIXAS))

    assert tempos[1].tempo_verde == 45
    assert tempos[1].ajuste == AjusteAplicado.MAXIMO_LIMITADO
    # O tempo que A não pôde usar vai para B
    assert tempos[2].tempo_verde == 35


def test_ciclo_encurta_quando_todas_as_vias_atingem_o_maximo():
    resultado = calcular_ciclo([via(1, 10, maximo=30), via(2, 10, maximo=30)], 90, FAIXAS)

    assert [t.tempo_verde for t in resultado.tempos] == [30, 30]
    assert resultado.duracao_total == 70  # 60 s de verde + 10 s de entreverdes


def test_minimos_prevalecem_mesmo_se_excederem_o_ciclo():
    resultado = calcular_ciclo([via(i, 5, minimo=30) for i in range(1, 4)], 60, FAIXAS)

    assert all(t.tempo_verde == 30 for t in resultado.tempos)
    assert resultado.duracao_total == 105  # 90 s de verde + 15 s de entreverdes


def test_sem_veiculos_distribui_igualmente():
    tempos = por_via(calcular_ciclo([via(1, 0), via(2, 0)], 90, FAIXAS))

    assert tempos[1].tempo_verde == tempos[2].tempo_verde == 40
    assert tempos[1].ajuste == AjusteAplicado.DISTRIBUICAO_IGUAL


def test_arredondamento_preserva_o_verde_disponivel():
    resultado = calcular_ciclo(
        [via(1, 1), via(2, 1), via(3, 1)],
        95,
        FAIXAS,
    )
    verdes = [t.tempo_verde for t in resultado.tempos]

    assert resultado.verde_disponivel == 80
    assert sum(verdes) == 80
    assert max(verdes) - min(verdes) <= 1


def test_vermelho_de_cada_via_completa_o_ciclo():
    resultado = calcular_ciclo([via(1, 30), via(2, 10)], 90, FAIXAS)

    for tempo in resultado.tempos:
        assert tempo.tempo_verde + tempo.tempo_amarelo + tempo.tempo_vermelho == 90


@pytest.mark.parametrize(
    ("veiculos", "faixas", "esperado"),
    [
        (5, 1, ClassificacaoFluxo.BAIXO),
        (6, 1, ClassificacaoFluxo.MODERADO),
        (30, 2, ClassificacaoFluxo.MODERADO),
        (25, 1, ClassificacaoFluxo.ALTO),
        (26, 1, ClassificacaoFluxo.CRITICO),
        (60, 3, ClassificacaoFluxo.ALTO),
    ],
)
def test_classificacao_por_veiculos_por_faixa(veiculos, faixas, esperado):
    assert FAIXAS.classificar(veiculos, faixas) == esperado


def test_faixas_de_fluxo_devem_ser_crescentes():
    with pytest.raises(ValueError):
        FaixasFluxo(baixo=10, moderado=5, alto=20)


@pytest.mark.parametrize(
    "parametros",
    [
        {"quantidade_veiculos": -1},
        {"quantidade_faixas": 0},
        {"tempo_minimo_verde": 50, "tempo_maximo_verde": 40},
        {"tempo_amarelo": 0},
    ],
)
def test_entrada_invalida_e_rejeitada(parametros):
    base = dict(
        via_id=1,
        quantidade_veiculos=10,
        quantidade_faixas=1,
        tempo_minimo_verde=20,
        tempo_maximo_verde=70,
        tempo_amarelo=3,
    )
    with pytest.raises(ValueError):
        EntradaVia(**(base | parametros))


def test_exige_ao_menos_uma_via():
    with pytest.raises(ValueError):
        calcular_ciclo([], 90, FAIXAS)
