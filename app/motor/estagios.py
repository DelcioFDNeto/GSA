"""Agrupamento das vias em estágios e distribuição do verde entre eles (RF08–RF11).

Um estágio é o conjunto de vias que recebe verde ao mesmo tempo. Os tempos de um estágio
respeitam todas as suas vias: o verde mínimo é o maior mínimo, o máximo é o menor máximo
(nunca abaixo do mínimo) e o entreverde é o maior entre as vias.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from app.motor.classificacao import FaixasFluxo
from app.motor.demanda import calcular_demandas
from app.motor.modelos import AjusteAplicado, EntradaVia, ResultadoCalculo, TempoCalculado

TRAVADOS = (AjusteAplicado.MINIMO_GARANTIDO, AjusteAplicado.MAXIMO_LIMITADO)


@dataclass(frozen=True)
class Estagio:
    chave: str
    vias: tuple[EntradaVia, ...]

    @property
    def tempo_minimo_verde(self) -> int:
        return max(v.tempo_minimo_verde for v in self.vias)

    @property
    def tempo_maximo_verde(self) -> int:
        return max(self.tempo_minimo_verde, min(v.tempo_maximo_verde for v in self.vias))

    @property
    def tempo_amarelo(self) -> int:
        return max(v.tempo_amarelo for v in self.vias)

    @property
    def tempo_vermelho(self) -> int:
        return max(v.tempo_vermelho for v in self.vias)

    @property
    def entreverde(self) -> int:
        return self.tempo_amarelo + self.tempo_vermelho

    @property
    def veiculos_criticos(self) -> int:
        """Veículos da via mais carregada do estágio: é ela que define o verde necessário."""
        return max(v.quantidade_veiculos for v in self.vias)


def agrupar_estagios(entradas: Sequence[EntradaVia]) -> list[Estagio]:
    if not entradas:
        raise ValueError("é necessário ao menos uma via para calcular o ciclo")
    if len({e.via_id for e in entradas}) != len(entradas):
        raise ValueError("vias repetidas na entrada do cálculo")
    grupos: dict[str, list[EntradaVia]] = {}
    for entrada in entradas:
        chave = f"e{entrada.estagio}" if entrada.estagio is not None else f"v{entrada.via_id}"
        grupos.setdefault(chave, []).append(entrada)
    return [Estagio(chave, tuple(vias)) for chave, vias in grupos.items()]


def distribuir_verde(
    estagios: Sequence[Estagio],
    pesos: dict[str, float],
    verde_disponivel: int,
    ajuste_padrao: AjusteAplicado = AjusteAplicado.PROPORCIONAL,
) -> tuple[dict[str, int], dict[str, AjusteAplicado]]:
    """Divide o verde proporcionalmente aos pesos, travando estágios no mínimo (prioridade,
    RF10) ou no máximo (RF11) e redistribuindo o restante entre os demais."""
    por_chave = {e.chave: e for e in estagios}
    sem_peso = all(pesos[c] == 0 for c in por_chave)
    alocacao: dict[str, float] = {}
    ajustes: dict[str, AjusteAplicado] = {}
    livres = list(por_chave)
    restante = float(max(verde_disponivel, 0))

    # Cada iteração trava ao menos um estágio, então o laço executa no máximo len(estagios) vezes.
    while livres:
        peso_total = sum(pesos[c] for c in livres)
        if peso_total == 0:
            proposta = {c: restante / len(livres) for c in livres}
        else:
            proposta = {c: restante * pesos[c] / peso_total for c in livres}

        abaixo = [c for c in livres if proposta[c] < por_chave[c].tempo_minimo_verde]
        if abaixo:
            for c in abaixo:
                alocacao[c] = por_chave[c].tempo_minimo_verde
                ajustes[c] = AjusteAplicado.MINIMO_GARANTIDO
                restante -= alocacao[c]
                livres.remove(c)
            continue

        acima = [c for c in livres if proposta[c] > por_chave[c].tempo_maximo_verde]
        if acima:
            for c in acima:
                alocacao[c] = por_chave[c].tempo_maximo_verde
                ajustes[c] = AjusteAplicado.MAXIMO_LIMITADO
                restante -= alocacao[c]
                livres.remove(c)
            continue

        ajuste = AjusteAplicado.DISTRIBUICAO_IGUAL if sem_peso else ajuste_padrao
        for c in livres:
            alocacao[c] = proposta[c]
            ajustes[c] = ajuste
        break

    return _arredondar(por_chave, alocacao, ajustes), ajustes


def _arredondar(
    por_chave: dict[str, Estagio],
    alocacao: dict[str, float],
    ajustes: dict[str, AjusteAplicado],
) -> dict[str, int]:
    """Converte para segundos inteiros sem perder segundos do ciclo (maiores restos)."""
    verdes = {c: math.floor(t) for c, t in alocacao.items()}
    flexiveis = [c for c in alocacao if ajustes[c] not in TRAVADOS]
    sobra = round(sum(alocacao[c] for c in flexiveis)) - sum(verdes[c] for c in flexiveis)
    for c in sorted(
        flexiveis, key=lambda c: (-(alocacao[c] - verdes[c]), list(por_chave).index(c))
    ):
        if sobra <= 0:
            break
        if verdes[c] < por_chave[c].tempo_maximo_verde:
            verdes[c] += 1
            sobra -= 1
    return verdes


def montar_resultado(
    regra: str,
    entradas: Sequence[EntradaVia],
    estagios: Sequence[Estagio],
    verdes: dict[str, int],
    ajustes: dict[str, AjusteAplicado],
    duracao_configurada: int,
    verde_disponivel: int,
    faixas: FaixasFluxo,
    grau_saturacao: float | None = None,
) -> ResultadoCalculo:
    demandas = calcular_demandas(entradas)
    estagio_da_via = {v.via_id: e for e in estagios for v in e.vias}
    duracao_total = sum(verdes.values()) + sum(e.entreverde for e in estagios)
    tempos = []
    for entrada in entradas:
        estagio = estagio_da_via[entrada.via_id]
        verde = verdes[estagio.chave]
        tempos.append(
            TempoCalculado(
                via_id=entrada.via_id,
                quantidade_veiculos=entrada.quantidade_veiculos,
                demanda=demandas[entrada.via_id],
                classificacao=faixas.classificar(
                    entrada.quantidade_veiculos, entrada.quantidade_faixas
                ),
                tempo_verde=verde,
                tempo_amarelo=estagio.tempo_amarelo,
                tempo_vermelho=duracao_total - verde - estagio.tempo_amarelo,
                ajuste=ajustes[estagio.chave],
            )
        )
    return ResultadoCalculo(
        regra=regra,
        duracao_ciclo_configurada=duracao_configurada,
        verde_disponivel=verde_disponivel,
        duracao_total=duracao_total,
        tempos=tempos,
        grau_saturacao=grau_saturacao,
    )
