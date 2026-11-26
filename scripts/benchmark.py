"""RNF10 — mede o tempo de resposta do processamento de leituras e das consultas.

Roda a API em processo (sem rede) sobre um banco temporário, envia lotes de leituras para um
cruzamento de quatro vias (cada lote grava as leituras e gera um ciclo) e consulta a situação.

Uso: python -m scripts.benchmark --lotes 500
     python -m scripts.benchmark --database-url postgresql+psycopg://usuario:senha@host/banco_vazio
"""

import argparse
import os
import random
import secrets
import statistics
import tempfile
import time
from pathlib import Path


def percentil(valores: list[float], p: float) -> float:
    ordenados = sorted(valores)
    return ordenados[min(len(ordenados) - 1, int(round(p / 100 * (len(ordenados) - 1))))]


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark do processamento de leituras")
    parser.add_argument("--lotes", type=int, default=500)
    parser.add_argument("--database-url", default=None, help="padrão: SQLite temporário")
    args = parser.parse_args()

    pasta = tempfile.mkdtemp(prefix="gsa_benchmark_")
    url = args.database_url or f"sqlite:///{Path(pasta) / 'benchmark.db'}"
    chave = secrets.token_urlsafe(16)
    os.environ.update(
        {
            "GSA_DATABASE_URL": url,
            "GSA_CHAVE_API_DETECCAO": chave,
            "GSA_INTERVALO_VERIFICACAO_FALHAS": "0",
        }
    )

    # Importações depois das variáveis de ambiente, que configuram a aplicação
    from fastapi.testclient import TestClient

    from app.db.base import Base
    from app.db.session import SessionLocal, engine
    from app.main import app
    from app.models import Direcao
    from app.schemas.cruzamento import CruzamentoCreate
    from app.schemas.semaforo import SemaforoCreate
    from app.schemas.via import ViaCreate
    from app.services.cruzamento_service import CruzamentoService
    from app.services.via_service import SemaforoService, ViaService

    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        cruzamento = CruzamentoService(db).criar(
            CruzamentoCreate(nome="Benchmark", latitude=0, longitude=0, duracao_ciclo=120)
        )
        vias = []
        for direcao in (Direcao.NORTE, Direcao.SUL, Direcao.LESTE, Direcao.OESTE):
            via = ViaService(db).criar(
                cruzamento.id, ViaCreate(nome=direcao.value, direcao=direcao, quantidade_faixas=2)
            )
            SemaforoService(db).criar(
                via.id,
                SemaforoCreate(tempo_minimo_verde=15, tempo_maximo_verde=60, tempo_amarelo=3),
            )
            vias.append(via.id)

    sorteio = random.Random(10)
    cabecalhos = {"X-API-Key": chave}
    tempos_lote, tempos_situacao = [], []
    with TestClient(app) as cliente:
        inicio_total = time.perf_counter()
        for _ in range(args.lotes):
            payload = {
                "cruzamentoId": cruzamento.id,
                "leituras": [
                    {"viaId": v, "quantidadeVeiculos": sorteio.randint(0, 40)} for v in vias
                ],
            }
            inicio = time.perf_counter()
            resposta = cliente.post(
                f"/cruzamentos/{cruzamento.id}/leituras", json=payload, headers=cabecalhos
            )
            tempos_lote.append((time.perf_counter() - inicio) * 1000)
            assert resposta.status_code == 201 and resposta.json()["cicloGerado"]

            inicio = time.perf_counter()
            assert cliente.get(f"/cruzamentos/{cruzamento.id}/situacao").status_code == 200
            tempos_situacao.append((time.perf_counter() - inicio) * 1000)
        duracao_total = time.perf_counter() - inicio_total

    banco = "PostgreSQL" if url.startswith("postgresql") else "SQLite (arquivo)"
    print(f"Banco: {banco} · {args.lotes} lotes de 4 leituras (cada um gera e grava um ciclo)")
    print(f"{'Operação':<42}{'média':>9}{'p50':>9}{'p95':>9}{'máx':>9}  (ms)")
    for nome, valores in (
        ("POST /cruzamentos/{id}/leituras + ciclo", tempos_lote),
        ("GET /cruzamentos/{id}/situacao", tempos_situacao),
    ):
        print(
            f"{nome:<42}{statistics.mean(valores):>9.1f}{percentil(valores, 50):>9.1f}"
            f"{percentil(valores, 95):>9.1f}{max(valores):>9.1f}"
        )
    print(f"Vazão: {args.lotes / duracao_total:.0f} lotes por segundo (envio + consulta)")


if __name__ == "__main__":
    main()
