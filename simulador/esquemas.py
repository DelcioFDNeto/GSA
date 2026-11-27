"""Contratos JSON entre a interface do simulador e o seu servidor (camelCase, como a API)."""

from typing import Annotated, Literal

from pydantic import Field

from app.schemas.base import SchemaBase

Normalizada = Annotated[float, Field(ge=0, le=1)]

# Detecção no formato compacto [id do rastreio, classe COCO, x1, y1, x2, y2, confiança], com a
# caixa em coordenadas normalizadas do quadro (0 a 1, eixo y para baixo), como o YOLO entrega
# depois de dividir pela largura e pela altura da imagem.
Deteccao = tuple[
    Annotated[int, Field(ge=0)],
    Annotated[str, Field(min_length=1, max_length=20)],
    Normalizada,
    Normalizada,
    Normalizada,
    Normalizada,
    Normalizada,
]


class ZonaEntrada(SchemaBase):
    via_id: int = Field(gt=0)
    nome: str = Field(min_length=1, max_length=120)
    poligono: list[tuple[float, float]] = Field(min_length=3, max_length=32)


class SessaoCriar(SchemaBase):
    """Calibração da câmera sintética: uma zona (polígono) por via, como em exemplo_zonas.json."""

    cruzamento_id: int = Field(gt=0)
    zonas: list[ZonaEntrada] = Field(min_length=1, max_length=16)
    confianca_minima: float = Field(default=0.3, ge=0, le=1)
    tempo_inicial: float = Field(
        default=0, ge=0, description="Tempo simulado em que a primeira janela começa"
    )


class Quadro(SchemaBase):
    t: float = Field(ge=0, description="Tempo simulado do quadro, em segundos")
    deteccoes: list[Deteccao] = Field(default_factory=list, max_length=400)


class QuadrosEnviar(SchemaBase):
    # limites para um pedido não ocupar a API: 240 quadros = 2 min simulados a 2 quadros/s
    quadros: list[Quadro] = Field(min_length=1, max_length=240)
    vias_sem_envio: list[int] = Field(
        default_factory=list,
        max_length=16,
        description="Vias cuja câmera está em falha: ficam fora do lote enviado ao GSA",
    )


class PlanoFixoPedido(SchemaBase):
    tipo: Literal["igual", "ajustado"] = "igual"
    taxas: dict[int, Annotated[float, Field(ge=0, le=20_000)]] = Field(
        default_factory=dict, description="Demanda média de cada via, em veículos/hora"
    )
