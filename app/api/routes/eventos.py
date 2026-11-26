import asyncio
import json

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from app.core.eventos import canal

router = APIRouter(tags=["Tempo real"])

INTERVALO_PING = 15  # segundos


@router.get(
    "/eventos",
    summary="Eventos em tempo real (SSE)",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}, "description": "Fluxo de eventos"}},
)
async def eventos(
    request: Request,
    cruzamento_id: int | None = Query(None, alias="cruzamentoId", description="Filtrar"),
):
    """Server-Sent Events com novos ciclos (`ciclo`), leituras (`leituras`) e falhas (`falha`).
    Usado pelo painel em /painel; consumível com `EventSource` no navegador."""
    fila = canal.assinar()

    async def fluxo():
        try:
            yield "retry: 3000\n\n"
            while not await request.is_disconnected():
                try:
                    mensagem = await asyncio.wait_for(fila.get(), timeout=INTERVALO_PING)
                except TimeoutError:
                    yield ": ping\n\n"
                    continue
                dados = mensagem["dados"]
                if cruzamento_id is not None and dados.get("cruzamentoId") != cruzamento_id:
                    continue
                corpo = json.dumps(mensagem, ensure_ascii=False)
                yield f"event: {mensagem['tipo']}\ndata: {corpo}\n\n"
        finally:
            canal.cancelar(fila)

    cabecalhos = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(fluxo(), media_type="text/event-stream", headers=cabecalhos)
