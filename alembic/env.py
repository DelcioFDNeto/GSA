from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

import app.models  # noqa: F401  (registra os modelos no metadata)
from app.core.config import get_settings
from app.db.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
database_url = get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=database_url.startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Engine própria, sem o PRAGMA foreign_keys=ON da aplicação: no SQLite o Alembic recria
    # tabelas (modo batch) e a checagem de chaves estrangeiras impediria isso com dados gravados.
    engine = create_engine(database_url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        sqlite = connection.dialect.name == "sqlite"
        context.configure(
            connection=connection, target_metadata=target_metadata, render_as_batch=sqlite
        )
        with context.begin_transaction():
            context.run_migrations()
        if sqlite:
            violacoes = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
            if violacoes:
                raise RuntimeError(f"Migração deixou chaves estrangeiras inválidas: {violacoes}")


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
