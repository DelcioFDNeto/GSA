"""Sessões da câmera sintética: cada aba do simulador é uma câmera com o seu contador.

A contagem é a do sistema de detecção de exemplo (`deteccao.zonas`): cada id do rastreador conta
uma vez por janela, na zona em que o ponto de contato da caixa foi visto primeiro. A janela é
medida em TEMPO SIMULADO (o `t` de cada quadro), então acelerar a simulação não muda o que cada
contagem representa — importante para a regra de Webster, que converte a contagem em fluxo
usando o `intervaloContagem` do GSA.
"""

import asyncio
import math
import time
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field

from deteccao.zonas import Configuracao, ContadorJanela, ponto_de_contato

VALIDADE_S = 30 * 60  # sessão sem uso é descartada
MAXIMO_SESSOES = 32

Deteccao = tuple[int, str, float, float, float, float, float]


class SessaoInexistente(LookupError):
    pass


class SessaoSubstituida(RuntimeError):
    """Outra aba assumiu a câmera do mesmo cruzamento."""


@dataclass
class Sessao:
    id: str
    configuracao: Configuracao
    confianca_minima: float
    contador: ContadorJanela = field(init=False)
    inicio_janela: float = 0.0
    ultimo_tempo: float = -math.inf
    janelas_fechadas: int = 0
    substituida: bool = False
    usada_em: float = field(default_factory=time.monotonic)
    trava: asyncio.Lock = field(default_factory=asyncio.Lock)
    ultimo_plano: dict | None = None
    sequencia_plano: int = 0

    def __post_init__(self) -> None:
        self.contador = ContadorJanela(self.configuracao.zonas)

    @property
    def cruzamento_id(self) -> int:
        return self.configuracao.cruzamento_id

    @property
    def janela(self) -> float:
        return self.configuracao.janela_segundos

    def registrar_quadro(self, deteccoes: Iterable[Deteccao]) -> int:
        """Passa as detecções de um quadro ao contador, filtrando classe e confiança como o
        contador YOLO faz. Devolve quantas foram aceitas."""
        aceitas = 0
        for id_rastreio, classe, x1, y1, x2, y2, confianca in deteccoes:
            if classe not in self.configuracao.classes or confianca < self.confianca_minima:
                continue
            self.contador.registrar(id_rastreio, *ponto_de_contato(x1, y1, x2, y2))
            aceitas += 1
        return aceitas

    def janela_terminou(self, t: float) -> bool:
        return t - self.inicio_janela >= self.janela

    def fechar_janela(self, t: float) -> tuple[float, float, dict[int, int]]:
        """Fecha a janela corrente e devolve (início, fim, contagem por via)."""
        inicio = self.inicio_janela
        contagens = self.contador.fechar_janela()
        self.inicio_janela += self.janela
        if t - self.inicio_janela >= self.janela:
            # faltaram quadros (ex.: rede): realinha sem inventar janelas vazias
            self.inicio_janela = t - (t - self.inicio_janela) % self.janela
        self.janelas_fechadas += 1
        return inicio, inicio + self.janela, contagens


class RepositorioSessoes:
    """Sessões em memória (a API roda em um processo, como o canal de eventos)."""

    def __init__(self, validade_s: float = VALIDADE_S, maximo: int = MAXIMO_SESSOES) -> None:
        self.validade_s = validade_s
        self.maximo = maximo
        self._sessoes: dict[str, Sessao] = {}
        self._ativa: dict[int, str] = {}

    def criar(self, configuracao: Configuracao, confianca_minima: float) -> Sessao:
        self._expirar()
        anterior = self._ativa.get(configuracao.cruzamento_id)
        if anterior in self._sessoes:
            self._sessoes[anterior].substituida = True
        while len(self._sessoes) >= self.maximo:
            mais_antiga = min(self._sessoes.values(), key=lambda s: s.usada_em)
            self._remover(mais_antiga.id)
        sessao = Sessao(uuid.uuid4().hex, configuracao, confianca_minima)
        self._sessoes[sessao.id] = sessao
        self._ativa[configuracao.cruzamento_id] = sessao.id
        return sessao

    def obter(self, sessao_id: str) -> Sessao:
        self._expirar()
        sessao = self._sessoes.get(sessao_id)
        if sessao is None:
            raise SessaoInexistente(sessao_id)
        if sessao.substituida:
            raise SessaoSubstituida(sessao_id)
        sessao.usada_em = time.monotonic()
        return sessao

    def encerrar(self, sessao_id: str) -> None:
        self._remover(sessao_id)

    def limpar(self) -> None:
        self._sessoes.clear()
        self._ativa.clear()

    def __len__(self) -> int:
        return len(self._sessoes)

    def _remover(self, sessao_id: str) -> None:
        sessao = self._sessoes.pop(sessao_id, None)
        if sessao and self._ativa.get(sessao.cruzamento_id) == sessao_id:
            del self._ativa[sessao.cruzamento_id]

    def _expirar(self) -> None:
        limite = time.monotonic() - self.validade_s
        for sessao_id in [s.id for s in self._sessoes.values() if s.usada_em < limite]:
            self._remover(sessao_id)
