#!/bin/sh
# Ponto de entrada do contêiner: migra o banco, popula a demonstração se pedido e sobe a API.
set -e
alembic upgrade head
if [ "${GSA_SEED_AO_INICIAR:-0}" = "1" ]; then
  python -m scripts.seed
fi
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
