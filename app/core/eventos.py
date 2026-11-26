"""Canal de eventos em tempo real (Server-Sent Events) usado pelo painel.

Os serviços publicam de dentro de threads (rotas síncronas); cada assinante é uma fila asyncio
do laço de eventos do servidor. Funciona em um único processo; com vários workers seria preciso
um intermediário externo (ex.: Redis).
"""

import asyncio
import threading
from datetime import UTC, datetime
from typing import Any

TAMANHO_FILA = 200


class CanalEventos:
    def __init__(self) -> None:
        self._assinantes: set[tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = set()
        self._trava = threading.Lock()

    def assinar(self) -> asyncio.Queue:
        fila: asyncio.Queue = asyncio.Queue(maxsize=TAMANHO_FILA)
        with self._trava:
            self._assinantes.add((asyncio.get_running_loop(), fila))
        return fila

    def cancelar(self, fila: asyncio.Queue) -> None:
        with self._trava:
            self._assinantes = {(laco, f) for laco, f in self._assinantes if f is not fila}

    @property
    def quantidade_assinantes(self) -> int:
        return len(self._assinantes)

    def publicar(self, tipo: str, dados: dict[str, Any]) -> None:
        mensagem = {"tipo": tipo, "em": datetime.now(UTC).isoformat(), "dados": dados}
        with self._trava:
            assinantes = list(self._assinantes)
        for laco, fila in assinantes:
            if not laco.is_closed():
                laco.call_soon_threadsafe(_entregar, fila, mensagem)


def _entregar(fila: asyncio.Queue, mensagem: dict) -> None:
    if fila.full():  # assinante lento: descarta o evento mais antigo
        fila.get_nowait()
    fila.put_nowait(mensagem)


canal = CanalEventos()
