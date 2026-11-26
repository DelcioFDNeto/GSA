"""Simulação comparativa: reprodutível e coerente (janela curta de pico para ser rápida)."""

from simulacao.modelo import AdaptativoWebster, FixoAjustado, FixoIgual, resumir, simular


def test_mesma_semente_gera_o_mesmo_resultado():
    a = resumir([simular(FixoIgual(), 7, 8, semente=3)])
    b = resumir([simular(FixoIgual(), 7, 8, semente=3)])
    assert a == b


def test_no_pico_de_demanda_alta_o_adaptativo_espera_menos_que_o_fixo():
    fator = 1.4
    fixo = resumir([simular(FixoAjustado(6, 22, fator), 7, 9, 1, fator)])
    adaptativo = resumir([simular(AdaptativoWebster(), 7, 9, 1, fator)])
    assert adaptativo["espera_media_s"] < fixo["espera_media_s"]
    assert adaptativo["fila_maxima"] < fixo["fila_maxima"]


def test_ciclos_do_webster_variam_entre_os_limites():
    resultado = simular(AdaptativoWebster(), 7, 9, semente=1, fator=1.4)
    assert min(resultado.ciclos) >= 40 and max(resultado.ciclos) <= 150 + 30
    assert len(set(resultado.ciclos)) > 1
