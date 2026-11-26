"""Gráficos SVG dos resultados da simulação, sem dependências externas."""

from xml.sax.saxutils import escape

# Cor segue a estratégia. Os dois planos fixos se distinguem também pelo traço (tracejado e
# pontilhado) e o ajustado usa cinza, por ser a referência de comparação.
CORES = {
    "fixo_igual": "#eb6834",
    "fixo_ajustado": "#6b6a65",
    "adaptativo_proporcional": "#1baf7a",
    "adaptativo_webster": "#2a78d6",
}
TRACOS = {"fixo_igual": ' stroke-dasharray="8 5"', "fixo_ajustado": ' stroke-dasharray="2 4"'}
TINTA, TINTA_2, GRADE = "#0b0b0b", "#52514e", "#e4e3df"


def _texto(x, y, conteudo, tam=12, cor=TINTA, ancora="start", peso="normal"):
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{tam}" fill="{cor}" '
        f'text-anchor="{ancora}" font-weight="{peso}">{escape(str(conteudo))}</text>'
    )


def linhas_por_hora(estrategias: list[dict], titulo: str) -> str:
    """Espera média por hora de chegada, uma linha por estratégia."""
    largura, altura = 900, 400
    esq, dir_, topo, base = 64, 24, 76, 48
    horas = sorted({int(h) for e in estrategias for h in e["espera_media_por_hora"]})
    maximo = max(v for e in estrategias for v in e["espera_media_por_hora"].values())
    escala_y = _escala_bonita(maximo)
    largura_plot = largura - esq - dir_
    altura_plot = altura - topo - base

    def x(h):
        return esq + (h - horas[0]) / (horas[-1] - horas[0]) * largura_plot

    def y(v):
        return topo + altura_plot - v / escala_y * altura_plot

    partes = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{largura}" height="{altura}" '
        f'viewBox="0 0 {largura} {altura}" font-family="DejaVu Sans, Arial, sans-serif">',
        f'<rect width="{largura}" height="{altura}" fill="#ffffff"/>',
        _texto(esq, 24, titulo, 15, TINTA, peso="bold"),
    ]
    for i in range(5):
        valor = escala_y * i / 4
        partes.append(
            f'<line x1="{esq}" x2="{esq + largura_plot}" y1="{y(valor):.1f}" y2="{y(valor):.1f}" '
            f'stroke="{GRADE}" stroke-width="1"/>'
        )
        partes.append(_texto(esq - 8, y(valor) + 4, f"{valor:.0f} s", 11, TINTA_2, "end"))
    for h in horas[::2]:
        partes.append(_texto(x(h), topo + altura_plot + 20, f"{h}h", 11, TINTA_2, "middle"))
    partes.append(
        _texto(esq + largura_plot / 2, altura - 8, "hora de chegada", 11, TINTA_2, "middle")
    )

    for e in estrategias:
        pontos = " ".join(
            f"{x(int(h)):.1f},{y(v):.1f}"
            for h, v in sorted(e["espera_media_por_hora"].items(), key=lambda kv: int(kv[0]))
        )
        tracejado = TRACOS.get(e["id"], "")
        partes.append(
            f'<polyline points="{pontos}" fill="none" stroke="{CORES[e["id"]]}" '
            f'stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"{tracejado}/>'
        )

    # Legenda no topo: cor identifica a estratégia; tracejado = tempo fixo, contínuo = adaptativo
    xl = esq
    for e in estrategias:
        tracejado = TRACOS.get(e["id"], "")
        partes.append(
            f'<line x1="{xl}" x2="{xl + 26}" y1="{topo - 12}" y2="{topo - 12}" '
            f'stroke="{CORES[e["id"]]}" stroke-width="3"{tracejado}/>'
        )
        nome = e["nome"].replace(" (GSA)", "").replace("Tempo fixo — ", "Fixo — ")
        partes.append(_texto(xl + 32, topo - 8, nome, 11, TINTA))
        xl += 32 + len(nome) * 6.2 + 16
    partes.append("</svg>")
    return "\n".join(partes)


def barras_resumo(cenarios: dict[str, list[dict]]) -> str:
    """Espera média do dia por estratégia, lado a lado para cada cenário."""
    largura, altura = 760, 330
    esq, topo, base = 250, 54, 40
    linhas = [(c, e) for c, lista in cenarios.items() for e in lista]
    maximo = max(e["espera_media_s"] for _, e in linhas)
    escala = _escala_bonita(maximo)
    largura_plot = largura - esq - 70
    barra, folga = 16, 6
    partes = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{largura}" height="{altura}" '
        f'viewBox="0 0 {largura} {altura}" font-family="DejaVu Sans, Arial, sans-serif">',
        f'<rect width="{largura}" height="{altura}" fill="#ffffff"/>',
        _texto(16, 24, "Espera média por veículo no dia (06h–22h)", 15, TINTA, peso="bold"),
    ]
    yy = topo
    for cenario, lista in cenarios.items():
        partes.append(_texto(16, yy + 10, f"Demanda {cenario}", 12, TINTA, peso="bold"))
        yy += 18
        for e in lista:
            w = e["espera_media_s"] / escala * largura_plot
            cor = CORES[e["id"]]
            partes.append(
                _texto(
                    esq - 10, yy + barra - 4, e["nome"].replace(" (GSA)", ""), 11, TINTA_2, "end"
                )
            )
            partes.append(
                f'<rect x="{esq}" y="{yy}" width="{max(w, 2):.1f}" height="{barra}" rx="3" '
                f'fill="{cor}"/>'
            )
            partes.append(_texto(esq + w + 6, yy + barra - 4, f"{e['espera_media_s']:.1f} s", 11))
            yy += barra + folga
        yy += 14
    partes.append("</svg>")
    svg = "\n".join(partes)
    return svg.replace(
        f'height="{altura}" viewBox="0 0 {largura} {altura}"',
        f'height="{yy + base - 20}" viewBox="0 0 {largura} {yy + base - 20}"',
    )


def _escala_bonita(maximo: float) -> float:
    for passo in (10, 20, 25, 50, 100, 200, 250, 500, 1000):
        if maximo <= passo * 4:
            return passo * 4
    return maximo
