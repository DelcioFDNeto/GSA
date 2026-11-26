"""Modelo de filas segundo a segundo de um cruzamento com dois estágios.

As estratégias adaptativas usam as mesmas regras do motor da API (app/motor). A demanda é
sintética — perfis horários com picos de manhã e à tarde — e serve para comparar estratégias
sob as mesmas chegadas de veículos, não para prever o resultado em uma via real.

Premissas (todas configuráveis neste módulo):
- chegadas de Poisson com taxa variando ao longo do dia;
- fluxo de saturação de 1800 veículos/hora por faixa durante o verde efetivo;
- 2 s de tempo perdido no início do verde e 2 s de verde aproveitado no amarelo;
- atraso de um veículo = instante em que cruza a linha de retenção − instante de chegada;
- veículos ainda na fila ao fim do período são contados como não atendidos.
"""

import math
import random
import statistics
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field

from app.motor import (
    DistribuicaoProporcional,
    EntradaVia,
    FaixasFluxo,
    PlanoFixo,
    ResultadoCalculo,
    Webster,
    calcular_ciclo,
)

FLUXO_SATURACAO = 1800  # veículos/hora por faixa
TEMPO_PERDIDO_INICIAL = 2  # s sem descarga no início do verde
GANHO_NO_AMARELO = 2  # s do amarelo ainda usados pelos veículos
AMARELO, VERMELHO_SEGURANCA = 3, 2
VERDE_MINIMO, VERDE_MAXIMO = 15, 60
CICLO_FIXO = 90
FAIXAS = FaixasFluxo(baixo=5, moderado=15, alto=25)


def _pico(hora: float, centro: float, largura: float) -> float:
    return math.exp(-((hora - centro) ** 2) / (2 * largura**2))


@dataclass(frozen=True)
class Aproximacao:
    via_id: int
    nome: str
    estagio: int
    faixas: int
    demanda: Callable[[float], float]  # veículos/hora em função da hora do dia


# Cruzamento fictício: avenida de 2 faixas por sentido × rua de 1 faixa por sentido.
# A avenida tem pico de manhã (sentido norte, rumo ao centro) e à tarde (sentido sul).
APROXIMACOES = (
    Aproximacao(
        1,
        "Avenida — sentido norte",
        1,
        2,
        lambda h: 450 + 850 * _pico(h, 8, 0.9) + 250 * _pico(h, 18, 1.2),
    ),
    Aproximacao(
        2,
        "Avenida — sentido sul",
        1,
        2,
        lambda h: 450 + 250 * _pico(h, 8, 0.9) + 850 * _pico(h, 18, 1.0),
    ),
    Aproximacao(
        3,
        "Rua — sentido leste",
        2,
        1,
        lambda h: 160 + 220 * _pico(h, 12.5, 1.0) + 120 * _pico(h, 17.5, 1.0),
    ),
    Aproximacao(
        4,
        "Rua — sentido oeste",
        2,
        1,
        lambda h: 140 + 180 * _pico(h, 12.5, 1.0) + 160 * _pico(h, 8, 1.0),
    ),
)


FATOR_DEMANDA = {"moderada": 1.0, "alta": 1.4}


def _entradas(contagens: dict[int, int]) -> list[EntradaVia]:
    return [
        EntradaVia(
            via_id=a.via_id,
            quantidade_veiculos=contagens.get(a.via_id, 0),
            quantidade_faixas=a.faixas,
            tempo_minimo_verde=VERDE_MINIMO,
            tempo_maximo_verde=VERDE_MAXIMO,
            tempo_amarelo=AMARELO,
            tempo_vermelho=VERMELHO_SEGURANCA,
            estagio=a.estagio,
        )
        for a in APROXIMACOES
    ]


@dataclass(frozen=True)
class Plano:
    verdes: dict[int, int]  # verde de cada estágio, na ordem em que abrem

    @property
    def duracao(self) -> int:
        return sum(self.verdes.values()) + len(self.verdes) * (AMARELO + VERMELHO_SEGURANCA)


def _plano(resultado: ResultadoCalculo) -> Plano:
    por_via = {t.via_id: t.tempo_verde for t in resultado.tempos}
    verdes: dict[int, int] = {}
    for a in APROXIMACOES:
        verdes.setdefault(a.estagio, por_via[a.via_id])
    return Plano(dict(sorted(verdes.items())))


class Estrategia:
    id: str
    nome: str

    def proximo_plano(self, contagens: dict[int, int], duracao_anterior: int) -> Plano:
        raise NotImplementedError


class FixoIgual(Estrategia):
    id, nome = "fixo_igual", "Tempo fixo — divisão igual (90 s)"

    def proximo_plano(self, contagens, duracao_anterior):
        return _plano(calcular_ciclo(_entradas({}), CICLO_FIXO, FAIXAS, PlanoFixo()))


class FixoAjustado(Estrategia):
    """Plano fixo calculado uma vez, por Webster, com a demanda média do dia — como um técnico
    de tráfego programaria um semáforo convencional."""

    id, nome = "fixo_ajustado", "Tempo fixo — ajustado à média do dia"

    def __init__(self, inicio: float, fim: float, fator: float = 1.0) -> None:
        horas = [inicio + i / 4 for i in range(int((fim - inicio) * 4))]
        intervalo = CICLO_FIXO
        medias = {
            a.via_id: round(statistics.mean(a.demanda(h) for h in horas) * fator * intervalo / 3600)
            for a in APROXIMACOES
        }
        regra = Webster(FLUXO_SATURACAO, intervalo, 40, 150)
        self.plano = _plano(calcular_ciclo(_entradas(medias), CICLO_FIXO, FAIXAS, regra))

    def proximo_plano(self, contagens, duracao_anterior):
        return self.plano


class AdaptativoProporcional(Estrategia):
    id, nome = "adaptativo_proporcional", "Adaptativo — proporcional (GSA)"

    def proximo_plano(self, contagens, duracao_anterior):
        regra = DistribuicaoProporcional()
        return _plano(calcular_ciclo(_entradas(contagens), CICLO_FIXO, FAIXAS, regra))


class AdaptativoWebster(Estrategia):
    id, nome = "adaptativo_webster", "Adaptativo — Webster (GSA)"

    def proximo_plano(self, contagens, duracao_anterior):
        regra = Webster(FLUXO_SATURACAO, max(duracao_anterior, 1), 40, 150)
        return _plano(calcular_ciclo(_entradas(contagens), CICLO_FIXO, FAIXAS, regra))


@dataclass
class Resultado:
    estrategia: str
    nome: str
    esperas: list[float] = field(default_factory=list)
    esperas_por_hora: dict[int, list[float]] = field(default_factory=dict)
    fila_maxima: int = 0
    nao_atendidos: int = 0
    ciclos: list[int] = field(default_factory=list)


def _poisson(rng: random.Random, media: float) -> int:
    limite, k, p = math.exp(-media), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limite:
            return k
        k += 1


def simular(
    estrategia: Estrategia, inicio: float, fim: float, semente: int, fator: float = 1.0
) -> Resultado:
    rng = random.Random(semente)
    filas = {a.via_id: deque() for a in APROXIMACOES}
    capacidade = dict.fromkeys(filas, 0.0)
    contagens = dict.fromkeys(filas, 0)
    resultado = Resultado(estrategia.id, estrategia.nome)
    total = int((fim - inicio) * 3600)
    t = 0
    plano = estrategia.proximo_plano(contagens, CICLO_FIXO)

    while t < total:
        fases = []
        for estagio, verde in plano.verdes.items():
            fases += [(estagio, "verde", verde), (estagio, "amarelo", AMARELO)]
            fases.append((None, "vermelho", VERMELHO_SEGURANCA))
        for estagio, tipo, duracao in fases:
            for k in range(duracao):
                if t >= total:
                    break
                hora = inicio + t / 3600
                for a in APROXIMACOES:
                    for _ in range(_poisson(rng, a.demanda(hora) * fator / 3600)):
                        filas[a.via_id].append(t)
                        contagens[a.via_id] += 1
                    descarrega = a.estagio == estagio and (
                        (tipo == "verde" and k >= TEMPO_PERDIDO_INICIAL)
                        or (tipo == "amarelo" and k < GANHO_NO_AMARELO)
                    )
                    fila = filas[a.via_id]
                    if descarrega and fila:
                        capacidade[a.via_id] += a.faixas * FLUXO_SATURACAO / 3600
                        while capacidade[a.via_id] >= 1 and fila:
                            chegada = fila.popleft()
                            capacidade[a.via_id] -= 1
                            espera = t - chegada
                            resultado.esperas.append(espera)
                            hora_chegada = int(inicio + chegada / 3600)
                            resultado.esperas_por_hora.setdefault(hora_chegada, []).append(espera)
                    else:
                        capacidade[a.via_id] = 0.0
                    resultado.fila_maxima = max(resultado.fila_maxima, len(fila))
                t += 1
        resultado.ciclos.append(plano.duracao)
        plano = estrategia.proximo_plano(contagens, plano.duracao)
        contagens = dict.fromkeys(filas, 0)

    resultado.nao_atendidos = sum(len(f) for f in filas.values())
    return resultado


def estrategias(inicio: float, fim: float, fator: float = 1.0) -> list[Estrategia]:
    return [
        FixoIgual(),
        FixoAjustado(inicio, fim, fator),
        AdaptativoProporcional(),
        AdaptativoWebster(),
    ]


def resumir(resultados: list[Resultado]) -> dict:
    """Média de várias execuções (sementes) da mesma estratégia."""
    esperas = [e for r in resultados for e in r.esperas]
    horas = sorted({h for r in resultados for h in r.esperas_por_hora})
    return {
        "id": resultados[0].estrategia,
        "nome": resultados[0].nome,
        "espera_media_s": round(statistics.mean(esperas), 1),
        "espera_p95_s": round(statistics.quantiles(esperas, n=20)[18], 1),
        "fila_maxima": round(statistics.mean(r.fila_maxima for r in resultados), 1),
        "veiculos_atendidos": round(statistics.mean(len(r.esperas) for r in resultados)),
        "nao_atendidos": round(statistics.mean(r.nao_atendidos for r in resultados), 1),
        "ciclo_medio_s": round(statistics.mean(c for r in resultados for c in r.ciclos), 1),
        "espera_media_por_hora": {
            str(h): round(
                statistics.mean(e for r in resultados for e in r.esperas_por_hora.get(h, [])), 1
            )
            for h in horas
        },
    }
