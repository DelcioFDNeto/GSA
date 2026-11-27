"""Simulador visual: a ponte câmera sintética → GSA (zonas.py, envio de leituras e planos)."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from app.main import app
from deteccao.zonas import montar_lote, ponto_de_contato
from simulacao.modelo import APROXIMACOES
from simulador import planos
from simulador.demanda import perfil_por_via
from simulador.servidor import montar_simulador

RAIZ = Path(__file__).resolve().parents[1]
API = "/simulador/api"
SEMAFORO = {"tempoMinimoVerde": 15, "tempoMaximoVerde": 60, "tempoAmarelo": 3, "tempoVermelho": 2}
# caixas (x1, y1, x2, y2) normalizadas cujo ponto de contato cai na zona de cada via
CAIXA = {
    "norte": (0.53, 0.70, 0.54, 0.73),
    "sul": (0.43, 0.20, 0.45, 0.25),
    "leste": (0.10, 0.505, 0.13, 0.515),
    "oeste": (0.80, 0.485, 0.81, 0.495),
}
PRIMEIRO_ID = {"norte": 1000, "sul": 2000, "leste": 3000, "oeste": 4000}


@pytest.fixture
def simulador(client):
    contexto = montar_simulador(app)  # idempotente; fala com este mesmo app (banco de teste)
    contexto.sessoes.limpar()
    yield contexto
    contexto.sessoes.limpar()


@pytest.fixture
def cruzamento_b(client, admin):
    """Cruzamento B do seed: avenida com 3 faixas por sentido (estágio 1) × rua (estágio 2)."""
    cruzamento = client.post(
        "/cruzamentos",
        json={
            "nome": "Cruzamento B",
            "latitude": 0,
            "longitude": 0,
            "duracaoCiclo": 120,
            "regraTemporizacao": "webster",
        },
        headers=admin,
    ).json()
    vias = {}
    for nome, direcao, faixas, estagio in (
        ("Avenida Central — sentido norte", "norte", 3, 1),
        ("Avenida Central — sentido sul", "sul", 3, 1),
        ("Rua Lateral — sentido leste", "leste", 1, 2),
        ("Rua Lateral — sentido oeste", "oeste", 1, 2),
    ):
        via = client.post(
            f"/cruzamentos/{cruzamento['id']}/vias",
            json={"nome": nome, "direcao": direcao, "quantidadeFaixas": faixas, "estagio": estagio},
            headers=admin,
        ).json()
        client.post(f"/vias/{via['id']}/semaforo", json=SEMAFORO, headers=admin)
        vias[direcao] = via["id"]
    return {"id": cruzamento["id"], "vias": vias}


def zonas(vias: dict) -> list[dict]:
    retangulos = {
        "norte": ((0.52, 0.56), (0.58, 1.0)),
        "sul": ((0.42, 0.0), (0.48, 0.44)),
        "leste": ((0.0, 0.5), (0.4, 0.52)),
        "oeste": ((0.6, 0.48), (1.0, 0.5)),
    }
    return [
        {
            "viaId": vias[direcao],
            "nome": direcao,
            "poligono": [[x0, y0], [x1, y0], [x1, y1], [x0, y1]],
        }
        for direcao, ((x0, y0), (x1, y1)) in retangulos.items()
    ]


def quadro(t: float, quantidades: dict[str, int], extras: list | None = None) -> dict:
    deteccoes = [
        [PRIMEIRO_ID[direcao] + i, "car", *CAIXA[direcao], 0.9]
        for direcao, quantidade in quantidades.items()
        for i in range(quantidade)
    ]
    return {"t": t, "deteccoes": deteccoes + (extras or [])}


def abrir_sessao(client, cruzamento_b, **extra) -> str:
    resposta = client.post(
        f"{API}/sessoes",
        json={"cruzamentoId": cruzamento_b["id"], "zonas": zonas(cruzamento_b["vias"]), **extra},
    )
    assert resposta.status_code == 201, resposta.text
    return resposta.json()["sessaoId"]


def enviar(client, sessao: str, quadros: list[dict], **extra) -> dict:
    resposta = client.post(f"{API}/sessoes/{sessao}/quadros", json={"quadros": quadros, **extra})
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def _status_do_simulador(habilitado: str) -> str:
    """Sobe o app em outro processo (a configuração é lida na importação) e consulta as rotas."""
    codigo = (
        "from fastapi.testclient import TestClient; from app.main import app; c = TestClient(app); "
        "print(c.get('/simulador/').status_code, c.get('/simulador/api/estado').status_code, "
        "c.get('/painel/').status_code)"
    )
    ambiente = {
        **os.environ,
        "GSA_DATABASE_URL": "sqlite://",
        "GSA_SIMULADOR_HABILITADO": habilitado,
    }
    saida = subprocess.run(
        [sys.executable, "-c", codigo],
        cwd=RAIZ,
        env=ambiente,
        capture_output=True,
        text=True,
        check=True,
    )
    return saida.stdout.strip()


def test_simulador_so_existe_quando_habilitado():
    assert _status_do_simulador("0") == "404 404 200"
    assert _status_do_simulador("1") == "200 200 200"


def test_interface_servida_em_rota_propria_sem_substituir_o_painel(client, simulador):
    pagina = client.get("/simulador/")
    assert pagina.status_code == 200 and "Simulador de tráfego" in pagina.text
    modulo = client.get("/simulador/js/app.js")
    assert modulo.status_code == 200 and "javascript" in modulo.headers["content-type"]
    assert client.get("/simulador/simulador.css").status_code == 200
    assert client.get("/painel/").status_code == 200
    assert "simulador" not in str(client.get("/openapi.json").json()["paths"])


def test_estado_sugere_o_cruzamento_com_mais_vias(client, simulador, cruzamento, cruzamento_b):
    estado = client.get(f"{API}/estado").json()
    assert estado["gsaOnline"] and estado["chaveConfigurada"] and estado["modoApi"] == "local"
    assert estado["cruzamentoPadrao"] == cruzamento_b["id"]
    assert "chave-de-teste" not in client.get(f"{API}/estado").text  # a chave não vai ao navegador


def test_configuracao_lida_da_api_com_plano_fixo_do_motor(client, simulador, cruzamento_b):
    dados = client.get(f"{API}/cruzamentos/{cruzamento_b['id']}/configuracao").json()
    vias = cruzamento_b["vias"]
    assert dados["janelaSegundos"] == dados["parametros"]["intervaloContagem"] == 90
    assert dados["cruzamento"]["regraTemporizacao"] == "webster"
    assert [
        (v["direcao"], v["quantidadeFaixas"], v["estagio"], v["eixo"]) for v in dados["vias"]
    ] == [
        ("norte", 3, 1, "ns"),
        ("sul", 3, 1, "ns"),
        ("leste", 1, 2, "lo"),
        ("oeste", 1, 2, "lo"),
    ]
    plano = dados["planoFixo"]
    assert plano["regra"] == "plano_fixo" and plano["duracao"] == plano["duracaoGsa"] == 120
    assert [(e["vias"], e["verde"], e["amarelo"], e["vermelho"]) for e in plano["estagios"]] == [
        ([vias["norte"], vias["sul"]], 55, 3, 2),
        ([vias["leste"], vias["oeste"]], 55, 3, 2),
    ]
    # tempoVermelho do ciclo é o total da via (120 − 55 − 3), não o vermelho de segurança (2)
    assert plano["tempos"][str(vias["leste"])]["vermelho"] == 62
    perfil = dados["perfilDemanda"]
    assert perfil["passoMinutos"] == 15 and len(perfil["vias"][str(vias["norte"])]) == 96
    assert dados["classes"] == ["car", "motorcycle", "bus", "truck"] and dados["avisos"] == []


def test_zonas_validadas_por_deteccao_zonas(client, simulador, cruzamento, cruzamento_b):
    base = {"cruzamentoId": cruzamento_b["id"]}
    em_pixels = zonas(cruzamento_b["vias"])[:1]
    em_pixels[0]["poligono"] = [[0, 0], [640, 0], [0, 480]]
    resposta = client.post(f"{API}/sessoes", json=base | {"zonas": em_pixels})
    assert resposta.status_code == 400 and "normalizadas" in resposta.json()["mensagem"]
    repetida = zonas(cruzamento_b["vias"])[:1] * 2
    resposta = client.post(f"{API}/sessoes", json=base | {"zonas": repetida})
    assert resposta.status_code == 400 and "apenas uma zona" in resposta.json()["mensagem"]
    alheia = zonas(cruzamento_b["vias"])
    alheia[0]["viaId"] = cruzamento["vias"][0]
    resposta = client.post(f"{API}/sessoes", json=base | {"zonas": alheia})
    assert resposta.status_code == 400 and "não pertencem" in resposta.json()["mensagem"]


def test_conta_veiculos_distintos_por_zona_e_envia_ao_gsa(client, simulador, cruzamento_b):
    vias = cruzamento_b["vias"]
    sessao = abrir_sessao(client, cruzamento_b)
    contagem = {"norte": 20, "sul": 10, "leste": 3, "oeste": 1}
    ruido = [
        [9001, "truck", *CAIXA["oeste"], 0.12],  # abaixo da confiança mínima
        [9002, "person", *CAIXA["oeste"], 0.95],  # classe fora da configuração
        [9003, "car", 0.95, 0.05, 0.97, 0.08, 0.9],  # fora de qualquer zona
    ]
    parcial = enviar(client, sessao, [quadro(t / 2, contagem, ruido) for t in range(1, 90)])
    assert parcial["envios"] == []
    esperado = {str(vias[d]): n for d, n in contagem.items()}
    assert parcial["janela"]["parcial"] == esperado  # mesmos ids em vários quadros contam uma vez

    resultado = enviar(client, sessao, [quadro(t / 2, contagem) for t in range(90, 182)])
    (envio,) = resultado["envios"]
    assert envio["janela"] == {"inicio": 0, "fim": 90.0}
    assert envio["status"] == 201 and envio["erro"] is None
    assert envio["lote"] == montar_lote(
        cruzamento_b["id"], {vias[d]: n for d, n in contagem.items()}
    )
    gravadas = client.get(f"/cruzamentos/{cruzamento_b['id']}/leituras").json()
    assert {(g["viaId"], g["quantidadeVeiculos"]) for g in gravadas} == {
        (vias[d], n) for d, n in contagem.items()
    }

    ciclo = envio["cicloGerado"]
    plano = envio["plano"]
    assert ciclo["regraAplicada"] == "webster" and ciclo["modoOperacao"] == "adaptativo"
    assert plano["sequencia"] == 1 and resultado["ultimoPlano"]["sequencia"] == 1
    assert plano["duracao"] == ciclo["duracaoTotal"] and plano["avisos"] == []
    assert [e["vias"] for e in plano["estagios"]] == [
        [vias["norte"], vias["sul"]],
        [vias["leste"], vias["oeste"]],
    ]
    for estagio in plano["estagios"]:
        assert estagio["vermelho"] == 2 and 15 <= estagio["verde"] <= 60
    for tempo in ciclo["tempos"]:
        soma = tempo["tempoVerde"] + tempo["tempoAmarelo"] + tempo["tempoVermelho"]
        assert soma == ciclo["duracaoTotal"]


def test_janela_em_tempo_simulado_com_realinhamento(client, simulador, cruzamento_b):
    sessao = abrir_sessao(client, cruzamento_b)
    um = {"norte": 1}
    assert enviar(client, sessao, [quadro(89.5, um)])["envios"] == []
    assert len(enviar(client, sessao, [quadro(90.0, um)])["envios"]) == 1
    # quadros que faltaram (ex.: rede): uma janela fechada e a contagem realinhada
    resultado = enviar(client, sessao, [quadro(400.0, um)])
    assert len(resultado["envios"]) == 1
    assert resultado["janela"]["inicio"] == 360.0
    # quadros reenviados são ignorados
    assert (
        enviar(client, sessao, [quadro(400.0, {"norte": 5})])["janela"]["parcial"][
            str(cruzamento_b["vias"]["norte"])
        ]
        == 0
    )


def test_via_sem_envio_fica_fora_do_lote_e_o_gsa_entra_no_modo_de_seguranca(
    client, simulador, cruzamento_b
):
    vias = cruzamento_b["vias"]
    sessao = abrir_sessao(client, cruzamento_b)
    contagem = {"norte": 12, "sul": 8, "leste": 2, "oeste": 3}
    resultado = enviar(
        client,
        sessao,
        [quadro(t / 2, contagem) for t in range(1, 182)],
        viasSemEnvio=[vias["oeste"]],
    )
    (envio,) = resultado["envios"]
    assert vias["oeste"] not in [item["viaId"] for item in envio["lote"]["leituras"]]
    assert envio["viasOmitidas"] == [vias["oeste"]]
    # a via nunca teve leitura: o GSA usa o plano fixo do modo de segurança
    assert envio["cicloGerado"]["modoOperacao"] == "contingencia"
    plano = envio["plano"]
    assert plano["modoOperacao"] == "contingencia" and plano["regra"] == "plano_fixo"
    assert "Rua Lateral — sentido oeste" in plano["motivoContingencia"]
    assert [e["verde"] for e in plano["estagios"]] == [55, 55]


def test_uma_camera_por_cruzamento(client, simulador, cruzamento_b):
    primeira = abrir_sessao(client, cruzamento_b)
    segunda = abrir_sessao(client, cruzamento_b, tempoInicial=30)
    antiga = client.post(f"{API}/sessoes/{primeira}/quadros", json={"quadros": [quadro(1, {})]})
    assert antiga.status_code == 409 and "Outra aba" in antiga.json()["mensagem"]
    nova = enviar(client, segunda, [quadro(31, {"norte": 1})])
    assert nova["janela"]["inicio"] == 30
    assert client.delete(f"{API}/sessoes/{segunda}").status_code == 204
    inexistente = client.post(
        f"{API}/sessoes/{segunda}/quadros", json={"quadros": [quadro(32, {})]}
    )
    assert inexistente.status_code == 404


def test_sem_chave_do_sistema_de_deteccao_o_erro_aparece(client, simulador, cruzamento_b):
    sessao = abrir_sessao(client, cruzamento_b)
    chave, simulador.cliente.chave = simulador.cliente.chave, None
    try:
        (envio,) = enviar(client, sessao, [quadro(90, {"norte": 3})])["envios"]
    finally:
        simulador.cliente.chave = chave
    assert envio["status"] == 0 and "GSA_CHAVE_API_DETECCAO" in envio["erro"]
    assert envio["plano"] is None


def test_planos_de_tempo_fixo_vem_do_motor(client, simulador, cruzamento_b):
    url = f"{API}/cruzamentos/{cruzamento_b['id']}/plano-fixo"
    igual = client.post(url, json={"tipo": "igual"}).json()
    assert [e["verde"] for e in igual["estagios"]] == [55, 55]
    vias = cruzamento_b["vias"]
    taxas = {vias["norte"]: 1950, vias["sul"]: 1050, vias["leste"]: 160, vias["oeste"]: 300}
    ajustado = client.post(url, json={"tipo": "ajustado", "taxas": taxas}).json()
    assert ajustado["regra"] == "webster" and ajustado["origem"] == "tempo_fixo_ajustado"
    assert 40 <= ajustado["duracao"] <= 150
    assert all(15 <= e["verde"] <= 60 for e in ajustado["estagios"])
    assert ajustado["estagios"][0]["verde"] > ajustado["estagios"][1]["verde"]


def _via(via_id, direcao, estagio, vermelho=2):
    return {
        "id": via_id,
        "nome": f"Via {via_id}",
        "direcao": direcao,
        "quantidadeFaixas": 1,
        "estagio": estagio,
        "semaforo": SEMAFORO | {"tempoVermelho": vermelho, "status": "ativo"},
    }


def _ciclo(verdes: dict[int, int], duracao: int) -> dict:
    return {
        "id": 1,
        "regraAplicada": "proporcional_com_limites",
        "duracaoTotal": duracao,
        "tempos": [
            {
                "viaId": via_id,
                "quantidadeVeiculos": 5,
                "demandaPercentual": 25.0,
                "classificacaoFluxo": "baixo",
                "tempoVerde": verde,
                "tempoAmarelo": 3,
                "tempoVermelho": duracao - verde - 3,
                "ajusteAplicado": "proporcional",
            }
            for via_id, verde in verdes.items()
        ],
    }


def test_plano_do_ciclo_usa_o_vermelho_de_seguranca_configurado():
    vias = [_via(1, "norte", 1), _via(2, "sul", 1), _via(3, "leste", 2, vermelho=4)]
    plano = planos.plano_do_ciclo(_ciclo({1: 40, 2: 40, 3: 30}, 40 + 5 + 30 + 7), vias)
    assert [(e["verde"], e["amarelo"], e["vermelho"]) for e in plano["estagios"]] == [
        (40, 3, 2),
        (30, 3, 4),
    ]
    assert plano["avisos"] == []
    # semáforo editado depois do cálculo: o plano avisa a divergência
    vias[2]["semaforo"]["tempoVermelho"] = 6
    assert planos.plano_do_ciclo(_ciclo({1: 40, 2: 40, 3: 30}, 82), vias)["avisos"]
    with pytest.raises(planos.PlanoInvalido, match="verdes diferentes"):
        planos.plano_do_ciclo(_ciclo({1: 40, 2: 35, 3: 30}, 82), vias)


def test_verificar_vias_aponta_estagio_inseguro_e_direcao_nao_desenhada():
    avisos = planos.verificar_vias(
        [_via(1, "norte", 1), _via(2, "leste", 1), _via(3, "nordeste", 2)]
    )
    assert any("se cruzam" in a for a in avisos)
    assert any("nordeste" in a for a in avisos)


def test_perfil_de_demanda_reaproveita_a_simulacao_e_escala_por_faixas():
    perfil = perfil_por_via([_via(1, "norte", 1) | {"quantidadeFaixas": 3}, _via(2, "oeste", 2)])
    norte = APROXIMACOES[0]
    assert len(perfil[1]) == 96
    assert perfil[1][32] == round(norte.demanda(8) / norte.faixas * 3, 1)  # 8h
    assert perfil[2][32] == round(APROXIMACOES[3].demanda(8), 1)


def test_ponto_de_contato_e_o_centro_da_base_da_caixa():
    assert ponto_de_contato(0.1, 0.2, 0.3, 0.6) == pytest.approx((0.2, 0.6))


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js não instalado")
def test_nucleo_javascript_do_simulador():
    """Movimento, filas, colisões, controlador, chegadas, câmera e controles (node --test)."""
    resultado = subprocess.run(
        ["node", "--test", "tests/js/"], cwd=RAIZ, capture_output=True, text=True, timeout=300
    )
    assert resultado.returncode == 0, resultado.stdout[-3000:] + resultado.stderr[-2000:]
