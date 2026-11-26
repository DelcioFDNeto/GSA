"""Eventos em tempo real (SSE) e painel web."""

import asyncio
import json
import threading

import pytest

from app.api.routes import eventos as rota_eventos
from app.core.eventos import TAMANHO_FILA, CanalEventos, canal
from tests.conftest import lote


def test_canal_entrega_eventos_publicados_de_outra_thread():
    async def cenario():
        canal_local = CanalEventos()
        fila = canal_local.assinar()
        thread = threading.Thread(target=canal_local.publicar, args=("ciclo", {"id": 1}))
        thread.start()
        mensagem = await asyncio.wait_for(fila.get(), timeout=2)
        thread.join()
        canal_local.cancelar(fila)
        return mensagem, canal_local.quantidade_assinantes

    mensagem, assinantes = asyncio.run(cenario())
    assert mensagem["tipo"] == "ciclo" and mensagem["dados"] == {"id": 1}
    assert "em" in mensagem
    assert assinantes == 0


def test_canal_descarta_o_mais_antigo_quando_assinante_esta_lento():
    async def cenario():
        canal_local = CanalEventos()
        fila = canal_local.assinar()
        for n in range(TAMANHO_FILA + 5):
            canal_local.publicar("leituras", {"n": n})
        await asyncio.sleep(0)  # deixa as entregas agendadas rodarem
        return fila

    fila = asyncio.run(cenario())
    assert fila.qsize() == TAMANHO_FILA
    assert fila.get_nowait()["dados"] == {"n": 5}


@pytest.fixture
def eventos_publicados(monkeypatch):
    publicados: list[tuple[str, dict]] = []
    monkeypatch.setattr(canal, "publicar", lambda tipo, dados: publicados.append((tipo, dados)))
    return publicados


def test_lote_publica_leituras_e_ciclo(client, cruzamento, deteccao, eventos_publicados):
    client.post(
        f"/cruzamentos/{cruzamento['id']}/leituras", json=lote(cruzamento, 30, 10), headers=deteccao
    )
    tipos = [tipo for tipo, _ in eventos_publicados]
    assert tipos == ["leituras", "ciclo"]
    leituras, ciclo = (dados for _, dados in eventos_publicados)
    assert leituras["cruzamentoId"] == cruzamento["id"]
    assert [item["quantidadeVeiculos"] for item in leituras["leituras"]] == [30, 10]
    assert ciclo["cruzamentoId"] == cruzamento["id"]
    assert [t["tempoVerde"] for t in ciclo["tempos"]] == [60, 20]  # já em camelCase


def test_simulacao_de_ciclo_nao_publica(client, cruzamento, deteccao, operador, eventos_publicados):
    url = f"/cruzamentos/{cruzamento['id']}"
    client.post(f"{url}/leituras", json=lote(cruzamento, 30, 10), headers=deteccao)
    eventos_publicados.clear()
    client.post(f"{url}/calcular-ciclo?simular=true", headers=operador)
    assert eventos_publicados == []


def test_falha_manual_publica_abertura_e_resolucao(
    client, cruzamento, operador, eventos_publicados
):
    falha = client.post(
        f"/cruzamentos/{cruzamento['id']}/falhas",
        json={"descricao": "Câmera obstruída"},
        headers=operador,
    ).json()
    client.post(f"/falhas/{falha['id']}/resolver", json={}, headers=operador)
    estados = [(tipo, dados["status"]) for tipo, dados in eventos_publicados]
    assert estados == [("falha", "aberta"), ("falha", "resolvida")]


def test_endpoint_sse_transmite_evento(client, monkeypatch):
    monkeypatch.setattr(rota_eventos, "INTERVALO_PING", 0.05)
    with client.stream("GET", "/eventos") as resposta:
        assert resposta.status_code == 200
        assert resposta.headers["content-type"].startswith("text/event-stream")
        linhas = resposta.iter_lines()
        assert next(linhas) == "retry: 3000"
        canal.publicar("ciclo", {"cruzamentoId": 7, "duracaoTotal": 90})
        recebidas = []
        for linha in linhas:
            recebidas.append(linha)
            if linha.startswith("data:"):
                break
    assert "event: ciclo" in recebidas
    corpo = json.loads(recebidas[-1].removeprefix("data: "))
    assert corpo["tipo"] == "ciclo" and corpo["dados"]["duracaoTotal"] == 90


def test_painel_e_servido_na_raiz(client):
    raiz = client.get("/", follow_redirects=False)
    assert raiz.status_code in (302, 307) and raiz.headers["location"] == "/painel/"
    pagina = client.get("/painel/")
    assert pagina.status_code == 200 and "Gestão Semafórica Adaptativa" in pagina.text
    assert client.get("/painel/painel.js").status_code == 200
    assert client.get("/painel/simulacao.json").json()["cenarios"]
