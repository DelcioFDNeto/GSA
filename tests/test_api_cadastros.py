"""RF01–RF03 e RF17 — cadastros, validações e ativação/desativação."""


def test_cadastro_completo_do_cruzamento(client, cruzamento):
    detalhe = client.get(f"/cruzamentos/{cruzamento['id']}").json()
    assert detalhe["status"] == "ativo"
    assert [via["nome"] for via in detalhe["vias"]] == ["Via A", "Via B"]
    assert detalhe["vias"][0]["semaforo"]["tempoMaximoVerde"] == 70


def test_dados_invalidos_retornam_400_com_detalhes(client, admin):
    resposta = client.post(
        "/cruzamentos", json={"nome": "", "latitude": -100, "longitude": 0}, headers=admin
    )
    assert resposta.status_code == 400
    assert len(resposta.json()["detalhes"]) == 2


def test_recurso_inexistente_retorna_404(client):
    assert client.get("/cruzamentos/999").status_code == 404
    assert client.get("/vias/999").status_code == 404
    assert client.get("/semaforos/999").status_code == 404
    assert client.get("/ciclos/999").status_code == 404


def test_atualiza_cruzamento_e_duracao_do_ciclo(client, admin, cruzamento):
    dados = {"nome": "Novo nome", "latitude": 1, "longitude": 2, "duracaoCiclo": 120}
    resposta = client.put(f"/cruzamentos/{cruzamento['id']}", json=dados, headers=admin)
    assert resposta.status_code == 200
    assert resposta.json()["duracaoCiclo"] == 120


def test_semaforo_sem_tempos_de_verde_usa_parametros(client, admin, cruzamento):
    via = client.post(
        f"/cruzamentos/{cruzamento['id']}/vias",
        json={"nome": "Via C", "direcao": "sul", "quantidadeFaixas": 1},
        headers=admin,
    ).json()
    semaforo = client.post(
        f"/vias/{via['id']}/semaforo", json={"tempoAmarelo": 3}, headers=admin
    ).json()
    parametros = client.get("/parametros").json()
    assert semaforo["tempoMinimoVerde"] == parametros["verdeMinimoPadrao"]
    assert semaforo["tempoMaximoVerde"] == parametros["verdeMaximoPadrao"]


def test_semaforo_duplicado_e_tempos_incoerentes(client, admin, cruzamento):
    via_id = cruzamento["vias"][0]
    duplicado = client.post(f"/vias/{via_id}/semaforo", json={"tempoAmarelo": 3}, headers=admin)
    assert duplicado.status_code == 400

    incoerente = {"tempoMinimoVerde": 50, "tempoMaximoVerde": 40, "tempoAmarelo": 3}
    semaforo_id = client.get(f"/vias/{via_id}/semaforo").json()["id"]
    resposta = client.put(f"/semaforos/{semaforo_id}", json=incoerente, headers=admin)
    assert resposta.status_code == 400


def test_desativar_e_reativar_sem_apagar(client, admin, cruzamento):
    url = f"/cruzamentos/{cruzamento['id']}"
    assert client.post(f"{url}/desativar", headers=admin).json()["status"] == "inativo"
    assert client.get(url).json()["vias"]  # registros preservados
    assert client.post(f"{url}/ativar", headers=admin).json()["status"] == "ativo"
    assert client.delete(url, headers=admin).json()["status"] == "inativo"
    inativos = client.get("/cruzamentos", params={"status": "inativo"}).json()
    assert [c["id"] for c in inativos] == [cruzamento["id"]]


def test_openapi_documenta_400_e_nao_422(client):
    esquema = client.get("/openapi.json").json()
    assert "422" not in str(esquema)
    assert "400" in esquema["paths"]["/cruzamentos"]["post"]["responses"]
