"""RF14–RF16 — situação atual, histórico e parâmetros do algoritmo."""

from tests.conftest import lote

PARAMETROS = {
    "duracaoCiclo": 100,
    "limiteFluxoBaixo": 2,
    "limiteFluxoModerado": 4,
    "limiteFluxoAlto": 6,
    "verdeMinimoPadrao": 10,
    "verdeMaximoPadrao": 50,
    "tempoMaximoSemLeitura": 120,
    "fluxoSaturacaoPorFaixa": 1800,
    "intervaloContagem": 90,
    "cicloMinimo": 40,
    "cicloMaximo": 150,
}


def test_situacao_atual(client, cruzamento, deteccao):
    url = f"/cruzamentos/{cruzamento['id']}"
    antes = client.get(f"{url}/situacao").json()
    assert antes["ultimoCiclo"] is None
    assert all(via["leituraDesatualizada"] for via in antes["vias"])

    client.post(f"{url}/leituras", json=lote(cruzamento, 30, 10), headers=deteccao)
    situacao = client.get(f"{url}/situacao").json()
    assert situacao["totalVeiculos"] == 40
    assert situacao["ultimoCiclo"]["duracaoTotal"] == 90
    via_a, via_b = situacao["vias"]
    assert via_a["ultimaLeitura"]["quantidadeVeiculos"] == 30
    assert via_a["leituraDesatualizada"] is False
    assert via_a["classificacaoFluxo"] == "moderado"  # 15 veículos por faixa
    assert [via_a["tempoVerdeRecomendado"], via_b["tempoVerdeRecomendado"]] == [60, 20]


def test_historico_resume_por_via(client, cruzamento, deteccao):
    url = f"/cruzamentos/{cruzamento['id']}"
    for quantidades in ((30, 10), (10, 20), (20, 0)):
        client.post(f"{url}/leituras", json=lote(cruzamento, *quantidades), headers=deteccao)

    historico = client.get(f"{url}/historico").json()
    assert historico["quantidadeLeituras"] == 6
    assert historico["quantidadeCiclos"] == 3
    via_a, via_b = historico["vias"]
    assert (via_a["mediaVeiculos"], via_a["minimoVeiculos"], via_a["maximoVeiculos"]) == (
        20,
        10,
        30,
    )
    assert via_b["mediaVeiculos"] == 10


def test_historico_com_periodo_invertido(client, cruzamento):
    params = {"inicio": "2026-12-01T00:00:00Z", "fim": "2026-11-01T00:00:00Z"}
    assert (
        client.get(f"/cruzamentos/{cruzamento['id']}/historico", params=params).status_code == 400
    )


def test_parametros_sao_alterados_pelo_administrador(client, admin, operador, cruzamento, deteccao):
    assert client.put("/parametros", json=PARAMETROS, headers=operador).status_code == 403
    resposta = client.put("/parametros", json=PARAMETROS, headers=admin)
    assert resposta.status_code == 200
    assert client.get("/parametros").json()["duracaoCiclo"] == 100

    url = f"/cruzamentos/{cruzamento['id']}"
    ciclo = client.post(f"{url}/leituras", json=lote(cruzamento, 30, 10), headers=deteccao).json()
    tempos = ciclo["cicloGerado"]["tempos"]
    assert ciclo["cicloGerado"]["duracaoCicloConfigurada"] == 100
    assert [t["classificacaoFluxo"] for t in tempos] == ["critico", "critico"]


def test_parametros_incoerentes_sao_rejeitados(client, admin):
    invertidos = PARAMETROS | {"limiteFluxoBaixo": 10}
    assert client.put("/parametros", json=invertidos, headers=admin).status_code == 400
