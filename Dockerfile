FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts
COPY simulacao ./simulacao

RUN useradd --create-home --uid 1000 gsa && mkdir -p /app/dados && chown gsa /app/dados
USER gsa

EXPOSE 8000
# Aplica as migrações pendentes e inicia a API (porta em $PORT, padrão 8000)
CMD ["sh", "scripts/iniciar.sh"]
