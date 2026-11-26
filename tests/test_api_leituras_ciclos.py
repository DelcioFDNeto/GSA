"""RF04–RF13 — recebimento de leituras, geração automática e histórico de ciclos."""

from tests.conftest import lote


def test_lote_gera_ciclo_do_exemplo_do_documento(client, cruzamento, deteccao):
    resposta = client.post(
        f"/cruzamentos/{cruzamento['id']}/leituras", json=lote(cruzamento, 30, 10), headers=deteccao
    )
    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["quantidadeRegistrada"] == 2
    ciclo = corpo["cicloGerado"]
    assert ciclo["persistido"] is True and ciclo["origem"] == "automatico"
    assert [t["tempoVerde"] for t in ciclo["tempos"]] == [60, 20]
    assert [t["demandaPercentual"] for t in ciclo["tempos"]] == [75.0, 25.0]
    assert ciclo["duracaoTotal"] == 90 and ciclo["totalVeiculos"] == 40


def test_ciclos_ficam_no_historico(client, cruzamento, deteccao):
    url = f"/cruzamentos/{cruzamento['id']}"
    client.post(f"{url}/leituras", json=lote(cruzamento, 30, 10), headers=deteccao)
    client.post(f"{url}/leituras", json=lote(cruzamento, 5, 35), headers=deteccao)

    historico = client.get(f"{url}/ciclos").json()
    assert len(historico) == 2
    mais_recente = historico[0]
    assert [t["quantidadeVeiculos"] for t in mais_recente["tempos"]] == [5, 35]
    assert mais_recente["regraAplicada"] == "proporcional_com_limites"

    detalhe = client.get(f"/ciclos/{mais_recente['id']}").json()
    assert detalhe == mais_recente


def test_calculo_manual_grava_e_simulacao_nao(client, cruzamento, deteccao, operador):
    url = f"/cruzamentos/{cruzamento['id']}"
    client.post(f"{url}/leituras", json=lote(cruzamento, 30, 10), headers=deteccao)

    manual = client.post(f"{url}/calcular-ciclo", headers=operador)
    assert manual.status_code == 201
    assert manual.json()["origem"] == "manual" and manual.json()["id"] is not None

    previa = client.post(f"{url}/calcular-ciclo", params={"simular": True}, headers=operador)
    assert previa.status_code == 200
    assert previa.json()["persistido"] is False and previa.json()["id"] is None

    assert len(client.get(f"{url}/ciclos").json()) == 2  # automático + manual


def test_calculo_manual_exige_login(client, cruzamento):
    assert client.post(f"/cruzamentos/{cruzamento['id']}/calcular-ciclo").status_code == 401


def test_envio_de_leituras_exige_chave_ou_token(client, cruzamento, operador):
    url = f"/cruzamentos/{cruzamento['id']}/leituras"
    dados = lote(cruzamento, 1, 1)
    assert client.post(url, json=dados).status_code == 401
    assert client.post(url, json=dados, headers={"X-API-Key": "errada"}).status_code == 401
    assert client.post(url, json=dados, headers=operador).status_code == 201


def test_validacoes_do_lote(client, cruzamento, deteccao, admin):
    url = f"/cruzamentos/{cruzamento['id']}/leituras"
    negativo = lote(cruzamento, -1, 3)
    assert client.post(url, json=negativo, headers=deteccao).status_code == 400

    divergente = lote(cruzamento, 1, 1) | {"cruzamentoId": 999}
    assert client.post(url, json=divergente, headers=deteccao).status_code == 400

    inexistente = {
        "cruzamentoId": cruzamento["id"],
        "leituras": [{"viaId": 999, "quantidadeVeiculos": 1}],
    }
    assert client.post(url, json=inexistente, headers=deteccao).status_code == 404

    client.post(f"/cruzamentos/{cruzamento['id']}/desativar", headers=admin)
    inativo = client.post(url, json=lote(cruzamento, 1, 1), headers=deteccao)
    assert inativo.status_code == 400


def test_via_de_outro_cruzamento_e_rejeitada(client, admin, cruzamento, deteccao):
    outro = client.post(
        "/cruzamentos", json={"nome": "Outro", "latitude": 0, "longitude": 0}, headers=admin
    ).json()
    dados = {
        "cruzamentoId": outro["id"],
        "leituras": [{"viaId": cruzamento["vias"][0], "quantidadeVeiculos": 1}],
    }
    resposta = client.post(f"/cruzamentos/{outro['id']}/leituras", json=dados, headers=deteccao)
    assert resposta.status_code == 400


def test_sem_semaforo_ativo_grava_leituras_e_registra_falha(client, admin, cruzamento, deteccao):
    for via_id in cruzamento["vias"]:
        semaforo = client.get(f"/vias/{via_id}/semaforo").json()
        dados = {k: semaforo[k] for k in ("tempoMinimoVerde", "tempoMaximoVerde", "tempoAmarelo")}
        client.put(
            f"/semaforos/{semaforo['id']}", json=dados | {"status": "manutencao"}, headers=admin
        )

    url = f"/cruzamentos/{cruzamento['id']}"
    resposta = client.post(f"{url}/leituras", json=lote(cruzamento, 8, 2), headers=deteccao).json()
    assert resposta["cicloGerado"] is None and resposta["avisos"]
    falhas = client.get(f"{url}/falhas", params={"status": "aberta"}).json()
    assert [f["tipo"] for f in falhas] == ["calculo_indisponivel"]

    # Um segundo lote não duplica a falha aberta
    client.post(f"{url}/leituras", json=lote(cruzamento, 8, 2), headers=deteccao)
    assert len(client.get(f"{url}/falhas").json()) == 1


def test_duracao_do_ciclo_por_cruzamento(client, admin, cruzamento, deteccao):
    url = f"/cruzamentos/{cruzamento['id']}"
    dados = {"nome": "C", "latitude": 0, "longitude": 0, "duracaoCiclo": 110}
    client.put(url, json=dados, headers=admin)
    ciclo = client.post(f"{url}/leituras", json=lote(cruzamento, 30, 10), headers=deteccao).json()
    assert ciclo["cicloGerado"]["duracaoCicloConfigurada"] == 110
    assert ciclo["cicloGerado"]["verdeDisponivel"] == 100


def test_historico_de_leituras_do_cruzamento(client, cruzamento, deteccao):
    url = f"/cruzamentos/{cruzamento['id']}"
    client.post(f"{url}/leituras", json=lote(cruzamento, 30, 10), headers=deteccao)
    client.post(
        f"/vias/{cruzamento['vias'][0]}/leituras", json={"quantidadeVeiculos": 7}, headers=deteccao
    )

    todas = client.get(f"{url}/leituras").json()
    assert len(todas) == 3 and todas[0]["quantidadeVeiculos"] == 7
    so_via_b = client.get(f"{url}/leituras", params={"viaId": cruzamento["vias"][1]}).json()
    assert [leitura["quantidadeVeiculos"] for leitura in so_via_b] == [10]
