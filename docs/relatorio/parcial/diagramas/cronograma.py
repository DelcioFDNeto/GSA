"""Gera o gráfico de Gantt do cronograma (cronograma.svg) sem dependências externas.

Versão do relatório parcial (01/10/2026).
Uso: python docs/relatorio/parcial/diagramas/cronograma.py
PNG: rsvg-convert -z 2.5 docs/relatorio/parcial/diagramas/cronograma.svg \
     -o docs/relatorio/parcial/img/cronograma.png
"""

from datetime import date, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

INICIO = date(2026, 9, 3)  # início do projeto (semana 1)
HOJE = date(2026, 10, 1)  # data do relatório parcial
FIM = date(2026, 11, 25)  # fim da semana 12

# (rótulo, responsável, início, fim, concluída) — responsáveis detalhados na tabela do relatório
FASES = [
    ("1 · Estruturação do projeto", "Délcio", date(2026, 9, 3), date(2026, 9, 9), True),
    ("2 · Modelagem do banco de dados", "João Pedro", date(2026, 9, 8), date(2026, 9, 16), True),
    ("3 · Cadastros (CRUD básico)", "Erick", date(2026, 9, 14), date(2026, 9, 23), True),
    ("4 · Recebimento de leituras", "Erick", date(2026, 9, 21), date(2026, 9, 28), True),
    (
        "5 · Motor de cálculo e testes",
        "Délcio · Nelson",
        date(2026, 9, 22),
        date(2026, 9, 30),
        True,
    ),
    ("Relatório parcial", "Nelson", date(2026, 9, 28), date(2026, 10, 1), True),
    (
        "6 · Geração de ciclos e histórico",
        "João Pedro",
        date(2026, 10, 5),
        date(2026, 10, 16),
        False,
    ),
    ("7 · Consultas e configurações", "Erick", date(2026, 10, 19), date(2026, 10, 30), False),
    (
        "8 · Documentação, segurança e testes",
        "Nelson · Délcio",
        date(2026, 11, 3),
        date(2026, 11, 13),
        False,
    ),
    ("Revisão e relatório final", "Equipe", date(2026, 11, 16), date(2026, 11, 19), False),
]

AZUL = "#2a78d6"
TINTA = "#0b0b0b"
TINTA_2 = "#52514e"
GRADE = "#e4e3df"
FUNDO = "#ffffff"

LARG, ROTULO, MARGEM_D = 640, 262, 14
TOPO, LINHA, BARRA = 64, 28, 14
ALT = TOPO + LINHA * len(FASES) + 56
DIAS = (FIM - INICIO).days
ESCALA = (LARG - ROTULO - MARGEM_D) / DIAS


def x(d: date) -> float:
    return ROTULO + (d - INICIO).days * ESCALA


def texto(px, py, conteudo, tam=12, cor=TINTA, ancora="start", peso="normal"):
    return (
        f'<text x="{px:.1f}" y="{py:.1f}" font-size="{tam}" fill="{cor}" '
        f'text-anchor="{ancora}" font-weight="{peso}">{escape(conteudo)}</text>'
    )


def gerar() -> str:
    partes = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{LARG}" height="{ALT}" '
        f'viewBox="0 0 {LARG} {ALT}" font-family="DejaVu Sans, Arial, sans-serif">',
        "<defs>",
        '<pattern id="hachura" width="6" height="6" patternUnits="userSpaceOnUse" '
        'patternTransform="rotate(45)">'
        f'<line x1="0" y1="0" x2="0" y2="6" stroke="{AZUL}" stroke-width="1.6"/></pattern>',
        "</defs>",
        f'<rect width="{LARG}" height="{ALT}" fill="{FUNDO}"/>',
    ]
    partes.append(texto(12, TOPO - 20, "Fase", 11, TINTA, "start", "bold"))
    # Grade semanal com rótulos S1, S2...
    semana, d = 1, INICIO
    while d <= FIM:
        partes.append(
            f'<line x1="{x(d):.1f}" y1="{TOPO - 14}" x2="{x(d):.1f}" '
            f'y2="{TOPO + LINHA * len(FASES)}" stroke="{GRADE}" stroke-width="1"/>'
        )
        if d + timedelta(days=7) <= FIM + timedelta(days=1):
            meio = x(d) + 3.5 * ESCALA
            partes.append(texto(meio, TOPO - 34, f"S{semana}", 11, TINTA, "middle", "bold"))
            partes.append(texto(meio, TOPO - 20, d.strftime("%d/%m"), 9, TINTA_2, "middle"))
        semana, d = semana + 1, d + timedelta(days=7)

    for i, (rotulo, _resp, ini, fim, feita) in enumerate(FASES):
        cy = TOPO + LINHA * i + LINHA / 2
        partes.append(texto(12, cy + 4, rotulo, 12, TINTA))
        x0, x1 = x(ini), x(fim + timedelta(days=1))
        y0 = cy - BARRA / 2
        if feita:
            partes.append(
                f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{x1 - x0:.1f}" height="{BARRA}" '
                f'rx="4" fill="{AZUL}"/>'
            )
        else:
            partes.append(
                f'<rect x="{x0 + 1:.1f}" y="{y0 + 1:.1f}" width="{x1 - x0 - 2:.1f}" '
                f'height="{BARRA - 2}" rx="4" fill="url(#hachura)" stroke="{AZUL}" '
                f'stroke-width="2"/>'
            )

    # Linha "hoje"
    xh = x(HOJE + timedelta(days=1))
    base = TOPO + LINHA * len(FASES)
    partes.append(
        f'<line x1="{xh:.1f}" y1="{TOPO - 8}" x2="{xh:.1f}" y2="{base + 6}" '
        f'stroke="{TINTA}" stroke-width="1.5" stroke-dasharray="4 3"/>'
    )
    partes.append(
        texto(xh, base + 20, "Relatório parcial · 01/10/2026", 11, TINTA, "middle", "bold")
    )

    # Legenda
    ly = ALT - 18
    partes.append(f'<rect x="12" y="{ly - 11}" width="28" height="12" rx="3" fill="{AZUL}"/>')
    partes.append(texto(46, ly, "Concluída", 11, TINTA))
    partes.append(
        f'<rect x="130" y="{ly - 10}" width="26" height="10" rx="3" fill="url(#hachura)" '
        f'stroke="{AZUL}" stroke-width="2"/>'
    )
    partes.append(texto(164, ly, "Prevista", 11, TINTA))
    partes.append(
        texto(
            LARG - MARGEM_D, ly, "S = semana do projeto (início em 03/09/2026)", 10, TINTA_2, "end"
        )
    )
    partes.append("</svg>")
    return "\n".join(partes)


if __name__ == "__main__":
    destino = Path(__file__).with_name("cronograma.svg")
    destino.write_text(gerar(), encoding="utf-8")
    print(f"Gerado {destino}")
