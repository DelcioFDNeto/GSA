"""Demanda base de cada via ao longo do dia, para as chegadas do simulador.

Reaproveita o perfil horário da simulação comparativa (`simulacao.modelo.APROXIMACOES`, com
picos às 8h e às 18h) e o escala pelo número de faixas de cada via, como faz
`scripts.demo_pitch`: o perfil é em veículos/hora por faixa da aproximação de mesmo sentido.
"""

from collections.abc import Sequence

from simulacao.modelo import APROXIMACOES, Aproximacao

PASSO_MINUTOS = 15

# "Avenida — sentido norte" -> norte; com fallback para a ordem norte, sul, leste, oeste
_POR_SENTIDO: dict[str, Aproximacao] = {a.nome.rsplit(" ", 1)[-1]: a for a in APROXIMACOES}
for _sentido, _aproximacao in zip(("norte", "sul", "leste", "oeste"), APROXIMACOES, strict=False):
    _POR_SENTIDO.setdefault(_sentido, _aproximacao)


def perfil_por_via(
    vias: Sequence[dict], passo_minutos: int = PASSO_MINUTOS
) -> dict[int, list[float]]:
    """Veículos/hora de cada via a cada `passo_minutos`, de 0h a 24h."""
    horas = [i * passo_minutos / 60 for i in range(24 * 60 // passo_minutos)]
    perfil = {}
    for via in vias:
        aproximacao = _POR_SENTIDO.get(via["direcao"])
        if aproximacao is None:
            continue
        por_faixa = [aproximacao.demanda(h) / aproximacao.faixas for h in horas]
        perfil[via["id"]] = [round(v * via["quantidadeFaixas"], 1) for v in por_faixa]
    return perfil
