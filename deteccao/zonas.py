"""Zonas de contagem por via e agregação em janelas de tempo.

Módulo sem dependências pesadas (não importa OpenCV nem YOLO), para poder ser testado no CI.
Coordenadas são normalizadas (0 a 1) em relação à largura e à altura do quadro, então a mesma
configuração serve para qualquer resolução do vídeo.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

CLASSES_PADRAO = ("car", "motorcycle", "bus", "truck")  # nomes do conjunto COCO usado pelo YOLO


@dataclass(frozen=True)
class Zona:
    via_id: int
    nome: str
    poligono: tuple[tuple[float, float], ...]

    def contem(self, x: float, y: float) -> bool:
        """Ray casting: o ponto está dentro do polígono?"""
        dentro = False
        pontos = self.poligono
        for i, (x1, y1) in enumerate(pontos):
            x2, y2 = pontos[i - 1]
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                dentro = not dentro
        return dentro


@dataclass(frozen=True)
class Configuracao:
    cruzamento_id: int
    janela_segundos: float
    zonas: tuple[Zona, ...]
    classes: tuple[str, ...] = CLASSES_PADRAO


def carregar_configuracao(caminho: str | Path) -> Configuracao:
    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    return configuracao_de_dicionario(dados)


def configuracao_de_dicionario(dados: dict) -> Configuracao:
    zonas = []
    for item in dados.get("zonas", []):
        poligono = tuple((float(x), float(y)) for x, y in item["poligono"])
        if len(poligono) < 3:
            raise ValueError(f"zona da via {item['viaId']}: o polígono precisa de 3 ou mais pontos")
        if not all(0 <= x <= 1 and 0 <= y <= 1 for x, y in poligono):
            raise ValueError(f"zona da via {item['viaId']}: use coordenadas normalizadas (0 a 1)")
        zonas.append(Zona(int(item["viaId"]), item.get("nome", f"via {item['viaId']}"), poligono))
    if not zonas:
        raise ValueError("a configuração precisa de ao menos uma zona")
    if len({z.via_id for z in zonas}) != len(zonas):
        raise ValueError("cada via pode ter apenas uma zona")
    janela = float(dados.get("janelaSegundos", 90))
    if janela <= 0:
        raise ValueError("janelaSegundos deve ser positivo")
    classes = tuple(dados.get("classes", CLASSES_PADRAO))
    return Configuracao(int(dados["cruzamentoId"]), janela, tuple(zonas), classes)


def ponto_de_contato(x1: float, y1: float, x2: float, y2: float) -> tuple[float, float]:
    """Centro da base da caixa (x1, y1, x2, y2), com o eixo y da imagem apontando para baixo:
    é onde o veículo toca a pista e o ponto que o contador usa para decidir a zona."""
    return (x1 + x2) / 2, y2


@dataclass
class ContadorJanela:
    """Conta veículos distintos (pelo id do rastreador) vistos em cada zona durante a janela.

    Usa o ponto central da base da caixa (onde o veículo toca a pista). Um veículo que aparece
    em duas zonas conta para a primeira em que foi visto.
    """

    zonas: tuple[Zona, ...]
    _vistos: dict[int, int] = field(default_factory=dict)  # id do rastreador -> via

    def registrar(self, id_rastreio: int, x: float, y: float) -> int | None:
        if id_rastreio in self._vistos:
            return self._vistos[id_rastreio]
        for zona in self.zonas:
            if zona.contem(x, y):
                self._vistos[id_rastreio] = zona.via_id
                return zona.via_id
        return None

    def parcial(self) -> dict[int, int]:
        contagem = {zona.via_id: 0 for zona in self.zonas}
        for via_id in self._vistos.values():
            contagem[via_id] += 1
        return contagem

    def fechar_janela(self) -> dict[int, int]:
        contagem = self.parcial()
        self._vistos.clear()
        return contagem


def montar_lote(cruzamento_id: int, contagens: dict[int, int]) -> dict:
    """Payload de POST /cruzamentos/{id}/leituras (RF04)."""
    return {
        "cruzamentoId": cruzamento_id,
        "leituras": [
            {"viaId": via_id, "quantidadeVeiculos": quantidade}
            for via_id, quantidade in sorted(contagens.items())
        ],
    }
