"""Cliente REST do GSA usado pelo simulador — o mesmo contrato do contador YOLO.

Por padrão fala com a própria API no mesmo processo (transporte ASGI), passando por rotas,
autenticação, validação e eventos em tempo real exatamente como uma requisição de rede. Com uma
URL (GSA_SIMULADOR_API_URL), fala com um GSA remoto, como faria a câmera de um cruzamento.
A chave do sistema de detecção fica só no servidor: o navegador nunca a recebe.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

URL_INTERNA = "http://gsa.interno"
TEMPO_LIMITE = 10.0


class ErroGSA(Exception):
    """A API do GSA não respondeu ou respondeu com erro."""

    def __init__(self, mensagem: str, status: int = 0) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.status = status


@dataclass
class RespostaEnvio:
    status: int
    corpo: dict[str, Any] | None
    latencia_ms: float
    erro: str | None = None


class ClienteGSA:
    def __init__(
        self,
        base_url: str,
        chave: str | None,
        fabrica_transporte: Callable[[], httpx.AsyncBaseTransport] | None = None,
        tempo_limite: float = TEMPO_LIMITE,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.chave = chave
        self._fabrica_transporte = fabrica_transporte
        self.tempo_limite = tempo_limite

    @property
    def remoto(self) -> bool:
        return self._fabrica_transporte is None

    def _cliente(self) -> httpx.AsyncClient:
        # Um cliente por operação: o simulador faz poucas chamadas (uma por janela de contagem)
        # e assim não há conexões presas a um laço de eventos que já terminou.
        transporte = self._fabrica_transporte() if self._fabrica_transporte else None
        return httpx.AsyncClient(
            base_url=self.base_url, transport=transporte, timeout=self.tempo_limite
        )

    async def obter(self, caminho: str, **parametros: Any) -> Any:
        try:
            async with self._cliente() as cliente:
                resposta = await cliente.get(caminho, params=parametros or None)
        except httpx.HTTPError as erro:
            raise ErroGSA(f"GSA indisponível em {self.base_url}: {erro}") from erro
        if resposta.status_code != 200:
            raise ErroGSA(_mensagem_de_erro(resposta), resposta.status_code)
        return resposta.json()

    async def enviar_leituras(self, cruzamento_id: int, lote: dict) -> RespostaEnvio:
        """POST /cruzamentos/{id}/leituras com a chave do sistema de detecção (RF04)."""
        if not self.chave:
            return RespostaEnvio(0, None, 0.0, "GSA_CHAVE_API_DETECCAO não está definida")
        inicio = time.perf_counter()
        try:
            async with self._cliente() as cliente:
                resposta = await cliente.post(
                    f"/cruzamentos/{cruzamento_id}/leituras",
                    json=lote,
                    headers={"X-API-Key": self.chave},
                )
        except httpx.HTTPError as erro:
            latencia = (time.perf_counter() - inicio) * 1000
            return RespostaEnvio(0, None, latencia, f"falha de comunicação com o GSA: {erro}")
        latencia = (time.perf_counter() - inicio) * 1000
        if resposta.status_code != 201:
            return RespostaEnvio(resposta.status_code, None, latencia, _mensagem_de_erro(resposta))
        return RespostaEnvio(resposta.status_code, resposta.json(), latencia)


def _mensagem_de_erro(resposta: httpx.Response) -> str:
    try:
        corpo = resposta.json()
    except ValueError:
        return f"GSA respondeu {resposta.status_code}"
    mensagem = corpo.get("mensagem") if isinstance(corpo, dict) else None
    detalhes = corpo.get("detalhes") if isinstance(corpo, dict) else None
    texto = f"GSA respondeu {resposta.status_code}: {mensagem or corpo}"
    if detalhes:
        texto += " (" + "; ".join(detalhes) + ")"
    return texto
