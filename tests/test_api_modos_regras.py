"""Modo de segurança (plano fixo), regra de Webster e estágios pela API."""

from datetime import timedelta

from app.db.types import agora_utc
from app.models import OrigemCiclo
from app.services.ciclo_service import CicloService
from tests.conftest import lote


def _cruzamento(client, admin, regra="proporcional", vias=(("A", None), ("B", None)), minimo=5):
    cruzamento = client.post(
        "/cruzamentos",
        json={"nome": "C", "latitude": 0, "longitude": 0, "regraTemporizacao": regra},
        headers=admin,
    ).json()
    ids = []
    for nome, estagio in vias:
        via = client.post(
            f"/cruzamentos/{cruzamento['id']}/vias",
            json={"nome": nome, "direcao": "norte", "quantidadeFaixas": 1, "estagio": estagio},
            headers=admin,
        ).json()
        tempos = {"tempoMinimoVerde": minimo, "tempoMaximoVerde": 70, "tempoAmarelo": 3}
        client.post(
            f"/vias/{via['id']}/semaforo", json=tempos | {"tempoVermelho": 2}, headers=admin
        )
        ids.append(via["id"])
    return {"id": cruzamento["id"], "vias": ids}


def test_sem_leituras_o_calculo_usa_o_plano_fixo(client, operador, cruzamento):
    ciclo = client.post(f"/cruzamentos/{cruzamento['id']}/calcular-ciclo", headers=operador).json()
    assert ciclo["modoOperacao"] == "contingencia"
    assert ciclo["regraAplicada"] == "plano_fixo"
    assert [t["tempoVerde"] for t in ciclo["tempos"]] == [40, 40]
    assert "Via A" in ciclo["motivoContingencia"]


def test_leituras_antigas_acionam_o_modo_de_seguranca(client, db, cruzamento, deteccao):
    url = f"/cruzamentos/{cruzamento['id']}"
    normal = client.post(f"{url}/leituras", json=lote(cruzamento, 30, 10), headers=deteccao).json()
    assert normal["cicloGerado"]["modoOperacao"] == "adaptativo"
    assert client.get(f"{url}/situacao").json()["modoOperacao"] == "adaptativo"

    # Dez minutos depois, sem novas leituras (limite padrão: 300 s)
    depois = agora_utc() + timedelta(minutes=10)
    ciclo = CicloService(db).gerar(cruzamento["id"], OrigemCiclo.MANUAL, momento=depois)
    assert ciclo.modo_operacao == "contingencia"
    assert [t.tempo_verde for t in ciclo.tempos] == [40, 40]

    # Ao chegar um lote novo, volta ao adaptativo
    volta = client.post(f"{url}/leituras", json=lote(cruzamento, 30, 10), headers=deteccao).json()
    assert volta["cicloGerado"]["modoOperacao"] == "adaptativo"


def test_situacao_sem_leituras_indica_contingencia(client, cruzamento):
    situacao = client.get(f"/cruzamentos/{cruzamento['id']}/situacao").json()
    assert situacao["modoOperacao"] == "contingencia"
    assert situacao["regraTemporizacao"] == "proporcional"


def test_cruzamento_com_regra_de_webster(client, admin, deteccao):
    c = _cruzamento(client, admin, regra="webster")
    resposta = client.post(
        f"/cruzamentos/{c['id']}/leituras", json=lote(c, 18, 9), headers=deteccao
    ).json()
    ciclo = resposta["cicloGerado"]
    assert ciclo["regraAplicada"] == "webster"
    assert ciclo["grauSaturacao"] == 0.6
    assert ciclo["duracaoCicloConfigurada"] == 50  # (1,5·10 + 5) / (1 − 0,6)
    assert [t["tempoVerde"] for t in ciclo["tempos"]] == [27, 13]


def test_vias_do_mesmo_estagio_abrem_juntas(client, admin, deteccao):
    c = _cruzamento(client, admin, vias=(("Norte", 1), ("Sul", 1), ("Leste", 2)))
    corpo = {
        "cruzamentoId": c["id"],
        "leituras": [
            {"viaId": v, "quantidadeVeiculos": q}
            for v, q in zip(c["vias"], (30, 10, 20), strict=True)
        ],
    }
    ciclo = client.post(f"/cruzamentos/{c['id']}/leituras", json=corpo, headers=deteccao).json()
    verdes = [t["tempoVerde"] for t in ciclo["cicloGerado"]["tempos"]]
    assert verdes == [48, 48, 32]
    assert client.get(f"/vias/{c['vias'][0]}").json()["estagio"] == 1
