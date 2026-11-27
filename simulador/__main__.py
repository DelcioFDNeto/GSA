"""Sobe o GSA com o simulador visual, em um banco de demonstração próprio.

As leituras do simulador são sintéticas. Para não misturá-las com dados reais, este comando usa
por padrão o banco `gsa_simulador.db` (separado do `gsa.db`), aplica as migrações, popula os
dados de demonstração do `scripts.seed` se o banco estiver vazio e liga o simulador.

Uso:
  python -m simulador                       # http://127.0.0.1:8000/simulador/
  python -m simulador --porta 8080 --recriar
  python -m simulador --api-url https://gsa.exemplo.com   # câmera sintética de um GSA remoto
                                                          # (exige GSA_CHAVE_API_DETECCAO)
"""

import argparse
import os
import secrets
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
BANCO_DEMONSTRACAO = "sqlite:///./gsa_simulador.db"


def _apagar_banco_sqlite(url: str) -> None:
    caminho = Path(url.removeprefix("sqlite:///"))
    if not url.startswith("sqlite:///") or caminho.suffix != ".db":
        raise SystemExit("--recriar só apaga bancos SQLite em arquivo .db")
    if caminho.exists():
        caminho.unlink()
        print(f"Banco de demonstração apagado: {caminho}")


def _cruzamento_sugerido() -> tuple[int, str] | None:
    """O cruzamento com mais vias (no seed, o B: quatro aproximações em dois estágios)."""
    from app.db.session import SessionLocal
    from app.repositories.cruzamento_repository import CruzamentoRepository

    with SessionLocal() as db:
        repo = CruzamentoRepository(db)
        detalhes = [repo.obter_com_vias(c.id) for c in repo.listar()]
    ativos = [c for c in detalhes if c is not None and c.status == "ativo" and c.vias]
    if not ativos:
        return None
    melhor = max(ativos, key=lambda c: (len(c.vias), -c.id))
    return melhor.id, melhor.nome


def main() -> None:
    parser = argparse.ArgumentParser(description="GSA + simulador visual de tráfego")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--porta", type=int, default=int(os.environ.get("PORT", 8000)))
    parser.add_argument(
        "--banco", default=BANCO_DEMONSTRACAO, help=f"URL do banco (padrão {BANCO_DEMONSTRACAO})"
    )
    parser.add_argument("--recriar", action="store_true", help="apaga o banco SQLite antes")
    parser.add_argument("--sem-seed", action="store_true", help="não popula a demonstração")
    parser.add_argument("--api-url", help="URL de um GSA remoto (a câmera envia para ele)")
    args = parser.parse_args()

    os.chdir(RAIZ)  # alembic.ini e o banco SQLite relativo ficam na raiz do projeto
    sys.path.insert(0, str(RAIZ))
    os.environ["GSA_DATABASE_URL"] = args.banco
    os.environ["GSA_SIMULADOR_HABILITADO"] = "1"
    os.environ["GSA_SIMULADOR_API_URL"] = args.api_url or ""  # vazio = esta mesma API

    from app.core.config import get_settings

    get_settings.cache_clear()
    if not get_settings().chave_api_deteccao:
        if args.api_url:
            raise SystemExit("Defina GSA_CHAVE_API_DETECCAO com a chave do GSA remoto.")
        # chave efêmera, só deste processo: o navegador nunca a recebe
        os.environ["GSA_CHAVE_API_DETECCAO"] = secrets.token_urlsafe(32)
        get_settings.cache_clear()

    if args.recriar:
        _apagar_banco_sqlite(args.banco)

    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(str(RAIZ / "alembic.ini")), "head")
    if not args.sem_seed and not args.api_url:
        from scripts.seed import popular

        popular()

    base = f"http://{'127.0.0.1' if args.host in ('0.0.0.0', '::') else args.host}:{args.porta}"
    sugerido = None if args.api_url else _cruzamento_sugerido()
    consulta = f"?cruzamento={sugerido[0]}" if sugerido else ""
    print()
    print("Leituras SINTÉTICAS — banco de demonstração:", args.banco)
    if args.api_url:
        print("GSA remoto:", args.api_url)
    if sugerido:
        print(f"Cruzamento sugerido: {sugerido[0]} — {sugerido[1]}")
    print(f"Simulador:    {base}/simulador/{consulta}")
    painel = f"{args.api_url.rstrip('/')}/painel/" if args.api_url else f"{base}/painel/"
    print(f"Painel ao vivo: {painel}{consulta}")
    print()

    import uvicorn

    uvicorn.run("app.main:app", host=args.host, port=args.porta, log_level="info")


if __name__ == "__main__":
    main()
