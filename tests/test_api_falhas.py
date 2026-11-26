"""RF18 — falhas por ausência de leitura e registro manual."""

from datetime import timedelta

from app.db.types import agora_utc
from app.services.falha_service import FalhaService
from tests.conftest import lote


def test_ausencia_de_leitura_gera_falha_e_nova_leitura_resolve(client, db, cruzamento, deteccao):
    daqui_dez_minutos = agora_utc() + timedelta(minutes=10)
    novas = FalhaService(db).verificar_ausencia_leituras(daqui_dez_minutos)
    assert sorted(f.via_id for f in novas) == sorted(cruzamento["vias"])

    # Verificar de novo não duplica as falhas já abertas
    assert FalhaService(db).verificar_ausencia_leituras(daqui_dez_minutos) == []

    abertas = client.get("/falhas", params={"status": "aberta", "tipo": "sem_leitura"}).json()
    assert len(abertas) == 2

    client.post(
        f"/cruzamentos/{cruzamento['id']}/leituras", json=lote(cruzamento, 3, 4), headers=deteccao
    )
    resolvidas = client.get("/falhas", params={"status": "resolvida"}).json()
    assert len(resolvidas) == 2
    assert all(f["observacaoResolucao"] == "Leitura recebida" for f in resolvidas)


def test_verificacao_imediata_sem_atraso_nao_gera_falha(client, operador, cruzamento):
    resposta = client.post("/falhas/verificar", headers=operador)
    assert resposta.status_code == 200
    assert resposta.json()["novasFalhas"] == []


def test_cruzamento_inativo_nao_e_monitorado(client, db, admin, cruzamento):
    client.post(f"/cruzamentos/{cruzamento['id']}/desativar", headers=admin)
    futuro = agora_utc() + timedelta(hours=1)
    assert FalhaService(db).verificar_ausencia_leituras(futuro) == []


def test_registro_e_resolucao_manual(client, operador, cruzamento):
    url = f"/cruzamentos/{cruzamento['id']}/falhas"
    dados = {"viaId": cruzamento["vias"][0], "descricao": "Câmera obstruída"}
    falha = client.post(url, json=dados, headers=operador)
    assert falha.status_code == 201 and falha.json()["tipo"] == "manual"

    resolver = f"/falhas/{falha.json()['id']}/resolver"
    resolvida = client.post(resolver, json={"observacao": "Câmera limpa"}, headers=operador)
    assert resolvida.json()["status"] == "resolvida"
    assert client.post(resolver, json={}, headers=operador).status_code == 400


def test_falha_manual_com_via_de_outro_cruzamento(client, admin, operador, cruzamento):
    outro = client.post(
        "/cruzamentos", json={"nome": "Outro", "latitude": 0, "longitude": 0}, headers=admin
    ).json()
    dados = {"viaId": cruzamento["vias"][0], "descricao": "Teste"}
    resposta = client.post(f"/cruzamentos/{outro['id']}/falhas", json=dados, headers=operador)
    assert resposta.status_code == 400


def test_registro_manual_exige_login(client, cruzamento):
    resposta = client.post(f"/cruzamentos/{cruzamento['id']}/falhas", json={"descricao": "abc"})
    assert resposta.status_code == 401
