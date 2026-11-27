"""Controles da interface do simulador em um navegador de verdade (Playwright).

Opcional: roda só com GSA_TESTE_NAVEGADOR=1 e o pacote playwright instalado. Usa o Chrome ou o
Edge já instalados (GSA_TESTE_NAVEGADOR_CANAL escolhe; sem eles, o Chromium do Playwright).
Sobe `python -m simulador` em um banco temporário e exercita os controles da página.
"""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

if os.environ.get("GSA_TESTE_NAVEGADOR") != "1":
    pytest.skip("defina GSA_TESTE_NAVEGADOR=1 para o teste no navegador", allow_module_level=True)
sync_api = pytest.importorskip("playwright.sync_api")

RAIZ = Path(__file__).resolve().parents[1]


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def servidor(tmp_path_factory):
    porta = _porta_livre()
    banco = tmp_path_factory.mktemp("simulador") / "e2e.db"
    processo = subprocess.Popen(
        [sys.executable, "-m", "simulador", "--porta", str(porta), "--banco", f"sqlite:///{banco}"],
        cwd=RAIZ,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{porta}"
    try:
        for _ in range(120):
            try:
                if httpx.get(f"{base}/health", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.25)
        else:
            pytest.fail("o simulador não subiu")
        yield base
    finally:
        processo.terminate()
        processo.wait(timeout=15)


@pytest.fixture(scope="module")
def pagina(servidor):
    with sync_api.sync_playwright() as p:
        canais = [os.environ.get("GSA_TESTE_NAVEGADOR_CANAL"), "chrome", "msedge", None]
        navegador = None
        for canal in [c for i, c in enumerate(canais) if c not in canais[:i] or c is None]:
            try:
                navegador = p.chromium.launch(channel=canal) if canal else p.chromium.launch()
                break
            except Exception:  # canal não instalado: tenta o próximo
                continue
        if navegador is None:
            pytest.skip("nenhum navegador Chromium disponível")
        pag = navegador.new_page(viewport={"width": 1600, "height": 1000})
        erros: list[str] = []
        pag.on("pageerror", lambda e: erros.append(str(e)))
        pag.on("console", lambda m: erros.append(m.text) if m.type == "error" else None)
        pag.goto(f"{servidor}/simulador/")
        pag.wait_for_function("window.__simulador && window.__simulador.mundo", timeout=20000)
        pag.erros = erros
        yield pag
        navegador.close()


def estado(pagina, expressao: str):
    return pagina.evaluate(f"() => {{ const a = window.__simulador; return {expressao}; }}")


def test_carrega_o_cruzamento_b_parado(pagina):
    assert estado(pagina, "a.mundo.rodando") is False
    assert estado(pagina, "a.mundo.t") == 0
    assert "Iniciar" in pagina.inner_text("#btn-iniciar")
    assert estado(pagina, "a.mundo.geometria.vias.length") == 4
    assert pagina.locator("#cabecalho-vias th").count() == 5


def test_iniciar_velocidade_e_envio_da_primeira_janela_ao_gsa(pagina):
    pagina.click("#btn-iniciar")
    assert estado(pagina, "a.mundo.rodando") is True
    assert "Pausar" in pagina.inner_text("#btn-iniciar")
    pagina.click("[data-velocidade='10']")
    assert pagina.get_attribute("[data-velocidade='10']", "aria-pressed") == "true"
    assert estado(pagina, "a.mundo.velocidade") == 10
    pagina.wait_for_function("window.__simulador.ponte.janelasEnviadas >= 1", timeout=30000)
    pagina.wait_for_function(
        "document.getElementById('json-lote').textContent.includes('cruzamentoId')", timeout=5000
    )
    lote = pagina.inner_text("#json-lote")
    assert '"cruzamentoId"' in lote and '"leituras"' in lote
    assert estado(pagina, "a.ponte.ultimoPlano.origem") == "gsa"
    vias_no_lote = estado(pagina, "a.ponte.ultimoLote.leituras.map(l => l.viaId).sort()")
    assert vias_no_lote == sorted(estado(pagina, "a.mundo.geometria.vias.map(v => v.id)"))
    assert "online" in pagina.inner_text("#status-api")


def test_caixas_zonas_e_zoom(pagina):
    pagina.uncheck("#opt-caixas")
    assert estado(pagina, "a.opcoes.caixas") is False
    pagina.check("#opt-caixas")
    pagina.click("[data-zoom='2']")
    assert estado(pagina, "a.renderB.zoom") == 2
    pagina.check("#opt-zonas")
    assert estado(pagina, "a.opcoes.zonas") is True
    assert estado(pagina, "a.mundo.modoZona") == "aproximacao"
    assert estado(pagina, "a.renderB.zoom") == 2, "a zona da aproximação aparece em qualquer zoom"
    sessao = estado(pagina, "a.ponte.sessaoId")
    pagina.select_option("#sel-zona", "entrada")
    assert estado(pagina, "a.mundo.modoZona") == "entrada"
    assert estado(pagina, "a.renderB.zoom") == 1, "a faixa de entrada fica na borda do quadro"
    pagina.wait_for_function(
        f"window.__simulador.ponte.sessaoId && window.__simulador.ponte.sessaoId !== '{sessao}'"
    )
    pagina.select_option("#sel-zona", "aproximacao")


def test_demanda_pico_fluxo_congestionamento_e_falha_de_camera(pagina):
    pagina.click("[data-preset='manha']")
    assert estado(pagina, "a.mundo.horaAtual()") == 8
    via = estado(pagina, "a.mundo.geometria.vias[0].id")
    antes = estado(pagina, f"a.mundo.taxaDaVia({via})")
    pagina.locator("#fluxos li").first.locator("button").last.click()
    assert estado(pagina, f"a.mundo.fator({via})") == 1.1
    assert estado(pagina, f"a.mundo.taxaDaVia({via})") == pytest.approx(antes * 1.1)
    pagina.select_option("#sel-congestionamento", "ns")
    assert estado(pagina, "a.mundo.demanda.congestionamento.eixo") == "ns"
    pagina.select_option("#sel-falha", str(via))
    assert estado(pagina, "a.ponte.viasSemEnvio") == [via]
    assert pagina.is_visible("#nota-falha")
    pagina.select_option("#sel-falha", "")
    pagina.select_option("#sel-congestionamento", "")


def test_modo_comparativo_com_as_mesmas_chegadas(pagina):
    pagina.check("#opt-comparar")
    pagina.wait_for_function(
        "window.__simulador.mundo.a !== null && window.__simulador.mundo.t > 30", timeout=30000
    )
    assert pagina.is_visible("#tela-a") and pagina.is_visible("#cartao-comparacao")
    chegadas = estado(pagina, "[a.mundo.a.estat.chegadas, a.mundo.b.estat.chegadas]")
    assert chegadas[0] == chegadas[1] > 0
    assert pagina.locator("#comparacao tr").count() == 7


def test_pausar_reiniciar_e_atalhos(pagina):
    pagina.click("#btn-iniciar")
    parado = estado(pagina, "a.mundo.t")
    time.sleep(0.5)
    assert estado(pagina, "a.mundo.t") == parado
    pagina.keyboard.press("Space")
    pagina.wait_for_function(f"window.__simulador.mundo.t > {parado}", timeout=5000)
    pagina.click("#btn-reiniciar")
    pagina.wait_for_function("window.__simulador.mundo.t < 5", timeout=5000)
    assert estado(pagina, "a.mundo.rodando") is True
    assert estado(pagina, "a.mundo.velocidade") == 10, "o reinício mantém a velocidade"
    pagina.keyboard.press("1")
    assert estado(pagina, "a.mundo.velocidade") == 1


def test_sem_erros_no_console(pagina):
    assert pagina.erros == []
