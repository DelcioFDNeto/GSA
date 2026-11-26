"""Compara tempo fixo e controle adaptativo em um cruzamento simulado (pitch / RNF10).

Roda dois cenários de demanda (moderada e alta, +40%) com várias sementes e grava:
- app/painel/simulacao.json e app/painel/graficos/*.svg (lidos pelo painel em /painel);
- docs/img/simulacao_*.svg e .png (gráficos para relatório e apresentação).

Uso: python -m scripts.simulacao_comparativa --sementes 5
Os resultados vêm de um modelo de filas com demanda sintética (premissas em simulacao/modelo.py);
servem para comparar estratégias sob as mesmas chegadas, não como medição em via real.
"""

import argparse
import json
import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from simulacao import graficos
from simulacao.modelo import (
    AMARELO,
    CICLO_FIXO,
    FATOR_DEMANDA,
    FLUXO_SATURACAO,
    GANHO_NO_AMARELO,
    TEMPO_PERDIDO_INICIAL,
    VERDE_MAXIMO,
    VERDE_MINIMO,
    VERMELHO_SEGURANCA,
    estrategias,
    resumir,
    simular,
)

RAIZ = Path(__file__).resolve().parents[1]
INICIO, FIM = 6, 22


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulação tempo fixo × adaptativo")
    parser.add_argument("--sementes", type=int, default=5)
    args = parser.parse_args()

    inicio_execucao = time.perf_counter()
    cenarios = {}
    for cenario, fator in FATOR_DEMANDA.items():
        resumos = []
        for estrategia in estrategias(INICIO, FIM, fator):
            execucoes = [
                simular(estrategia, INICIO, FIM, semente, fator)
                for semente in range(1, args.sementes + 1)
            ]
            resumos.append(resumir(execucoes))
        cenarios[cenario] = resumos

    dados = {
        "gerado_em": datetime.now(UTC).isoformat(timespec="seconds"),
        "periodo": f"{INICIO:02d}h–{FIM:02d}h",
        "sementes": args.sementes,
        "premissas": {
            "cruzamento": "avenida 2 faixas por sentido (estágio 1) × rua 1 faixa por sentido "
            "(estágio 2)",
            "demanda": "sintética, com picos às 8h e às 18h; cenário alto = +40%",
            "fluxo_saturacao_veic_h_faixa": FLUXO_SATURACAO,
            "tempo_perdido_inicio_verde_s": TEMPO_PERDIDO_INICIAL,
            "verde_aproveitado_no_amarelo_s": GANHO_NO_AMARELO,
            "amarelo_s": AMARELO,
            "vermelho_seguranca_s": VERMELHO_SEGURANCA,
            "verde_minimo_maximo_s": [VERDE_MINIMO, VERDE_MAXIMO],
            "ciclo_tempo_fixo_s": CICLO_FIXO,
        },
        "cenarios": cenarios,
    }

    destino_json = RAIZ / "app" / "painel" / "simulacao.json"
    destino_json.parent.mkdir(parents=True, exist_ok=True)
    destino_json.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")

    imagens = RAIZ / "docs" / "img"
    graficos_painel = RAIZ / "app" / "painel" / "graficos"
    graficos_painel.mkdir(parents=True, exist_ok=True)
    svgs = {
        "simulacao_resumo": graficos.barras_resumo(cenarios),
        "simulacao_por_hora_moderada": graficos.linhas_por_hora(
            cenarios["moderada"], "Espera média por hora — demanda moderada"
        ),
        "simulacao_por_hora_alta": graficos.linhas_por_hora(
            cenarios["alta"], "Espera média por hora — demanda alta (+40%)"
        ),
    }
    for nome, svg in svgs.items():
        caminho = imagens / f"{nome}.svg"
        caminho.write_text(svg, encoding="utf-8")
        (graficos_painel / f"{nome}.svg").write_text(svg, encoding="utf-8")
        if shutil.which("rsvg-convert"):
            subprocess.run(
                ["rsvg-convert", "-z", "2.5", str(caminho), "-o", str(caminho.with_suffix(".png"))],
                check=True,
            )

    for cenario, resumos in cenarios.items():
        print(f"\nDemanda {cenario} ({args.sementes} sementes, {INICIO}h–{FIM}h)")
        print(f"{'Estratégia':<40}{'espera média':>14}{'p95':>8}{'fila máx':>10}{'ciclo':>8}")
        for r in resumos:
            print(
                f"{r['nome']:<40}{r['espera_media_s']:>12.1f} s{r['espera_p95_s']:>6.0f} s"
                f"{r['fila_maxima']:>10.0f}{r['ciclo_medio_s']:>6.0f} s"
            )
    print(f"\nGravado em {destino_json.relative_to(RAIZ)}, app/painel/graficos/ e docs/img/")
    print(f"Tempo de execução: {time.perf_counter() - inicio_execucao:.0f} s")


if __name__ == "__main__":
    main()
