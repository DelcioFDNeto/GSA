"""Lógica de contagem do sistema de detecção de exemplo (sem YOLO, sem OpenCV)."""

import json
from pathlib import Path

import pytest

from deteccao.zonas import (
    ContadorJanela,
    Zona,
    carregar_configuracao,
    configuracao_de_dicionario,
    montar_lote,
)

ESQUERDA = Zona(1, "esquerda", ((0, 0), (0.5, 0), (0.5, 1), (0, 1)))
DIREITA = Zona(2, "direita", ((0.5, 0), (1, 0), (1, 1), (0.5, 1)))
TRIANGULO = Zona(3, "triângulo", ((0.1, 0.9), (0.5, 0.1), (0.9, 0.9)))


@pytest.mark.parametrize(
    ("zona", "ponto", "esperado"),
    [
        (ESQUERDA, (0.25, 0.5), True),
        (ESQUERDA, (0.75, 0.5), False),
        (TRIANGULO, (0.5, 0.8), True),
        (TRIANGULO, (0.15, 0.2), False),
        (TRIANGULO, (0.85, 0.2), False),
    ],
)
def test_ponto_dentro_do_poligono(zona, ponto, esperado):
    assert zona.contem(*ponto) is esperado


def test_conta_veiculos_distintos_por_zona():
    contador = ContadorJanela((ESQUERDA, DIREITA))
    contador.registrar(10, 0.2, 0.5)
    contador.registrar(10, 0.25, 0.6)  # mesmo veículo em outro quadro
    contador.registrar(11, 0.3, 0.9)
    contador.registrar(12, 0.8, 0.5)
    assert contador.parcial() == {1: 2, 2: 1}


def test_veiculo_conta_para_a_primeira_zona_em_que_foi_visto():
    contador = ContadorJanela((ESQUERDA, DIREITA))
    assert contador.registrar(5, 0.4, 0.5) == 1
    assert contador.registrar(5, 0.6, 0.5) == 1  # cruzou para a outra zona
    assert contador.parcial() == {1: 1, 2: 0}


def test_veiculo_fora_das_zonas_nao_conta():
    contador = ContadorJanela((TRIANGULO,))
    assert contador.registrar(1, 0.05, 0.05) is None
    assert contador.parcial() == {3: 0}


def test_fechar_janela_zera_a_contagem():
    contador = ContadorJanela((ESQUERDA, DIREITA))
    contador.registrar(1, 0.1, 0.1)
    assert contador.fechar_janela() == {1: 1, 2: 0}
    assert contador.parcial() == {1: 0, 2: 0}
    contador.registrar(1, 0.1, 0.1)  # o mesmo veículo ainda na zona conta na nova janela
    assert contador.parcial() == {1: 1, 2: 0}


def test_lote_no_formato_da_api():
    assert montar_lote(4, {9: 3, 8: 0}) == {
        "cruzamentoId": 4,
        "leituras": [
            {"viaId": 8, "quantidadeVeiculos": 0},
            {"viaId": 9, "quantidadeVeiculos": 3},
        ],
    }


def test_lote_e_aceito_pela_api(client, cruzamento, deteccao):
    vias = cruzamento["vias"]
    lote = montar_lote(cruzamento["id"], {vias[0]: 30, vias[1]: 10})
    resposta = client.post(f"/cruzamentos/{cruzamento['id']}/leituras", json=lote, headers=deteccao)
    assert resposta.status_code == 201
    assert [t["tempoVerde"] for t in resposta.json()["cicloGerado"]["tempos"]] == [60, 20]


def test_configuracao_de_exemplo_e_valida():
    raiz = Path(__file__).resolve().parents[1]
    config = carregar_configuracao(raiz / "deteccao" / "exemplo_zonas.json")
    assert config.cruzamento_id == 1 and len(config.zonas) == 2
    assert "car" in config.classes


@pytest.mark.parametrize(
    ("alteracao", "mensagem"),
    [
        ({"zonas": []}, "ao menos uma zona"),
        ({"zonas": [{"viaId": 1, "poligono": [[0, 0], [1, 1]]}]}, "3 ou mais pontos"),
        ({"zonas": [{"viaId": 1, "poligono": [[0, 0], [640, 0], [0, 480]]}]}, "normalizadas"),
        ({"janelaSegundos": 0}, "positivo"),
    ],
)
def test_configuracao_invalida(alteracao, mensagem):
    base = json.loads(
        '{"cruzamentoId": 1, "zonas": [{"viaId": 1, "poligono": [[0,0],[1,0],[1,1]]}]}'
    )
    with pytest.raises(ValueError, match=mensagem):
        configuracao_de_dicionario(base | alteracao)


def test_zonas_repetidas_sao_recusadas():
    zona = {"viaId": 1, "poligono": [[0, 0], [1, 0], [1, 1]]}
    with pytest.raises(ValueError, match="apenas uma zona"):
        configuracao_de_dicionario({"cruzamentoId": 1, "zonas": [zona, zona]})
