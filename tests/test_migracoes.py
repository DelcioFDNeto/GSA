"""As migrações do Alembic criam o esquema dos modelos e preservam dados já gravados."""

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, text

import app.models  # noqa: F401
from app.core.config import get_settings
from app.db.base import Base


@pytest.fixture
def banco_migracao(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'migracao.db'}"
    monkeypatch.setenv("GSA_DATABASE_URL", url)
    get_settings.cache_clear()
    engine = create_engine(url)
    yield Config("alembic.ini"), engine
    engine.dispose()
    get_settings.cache_clear()


def test_migracoes_correspondem_aos_modelos(banco_migracao):
    config, engine = banco_migracao
    command.upgrade(config, "head")
    with engine.connect() as conexao:
        assert compare_metadata(MigrationContext.configure(conexao), Base.metadata) == []
    command.downgrade(config, "base")


def test_migracao_0002_preserva_dados_da_fase_5(banco_migracao):
    config, engine = banco_migracao
    command.upgrade(config, "0001")
    with engine.begin() as conexao:
        for sql in (
            "INSERT INTO cruzamentos (id, nome, latitude, longitude, status, criado_em, "
            "atualizado_em) VALUES (1, 'C', 0, 0, 'ativo', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
            "INSERT INTO vias (id, nome, direcao, quantidade_faixas, cruzamento_id) "
            "VALUES (5, 'V', 'norte', 1, 1)",
            "INSERT INTO semaforos (id, via_id, tempo_minimo_verde, tempo_maximo_verde, "
            "tempo_amarelo, tempo_vermelho, status) VALUES (9, 5, 20, 70, 3, 2, 'ativo')",
            "INSERT INTO ciclos_semaforicos (id, cruzamento_id, data_hora_inicio, duracao_total, "
            "regra_aplicada) VALUES (1, 1, CURRENT_TIMESTAMP, 90, 'proporcional_com_limites')",
            "INSERT INTO tempos_semaforicos (id, ciclo_id, semaforo_id, quantidade_veiculos, "
            "classificacao_fluxo, tempo_verde, tempo_amarelo, tempo_vermelho) "
            "VALUES (1, 1, 9, 10, 'baixo', 60, 3, 27)",
        ):
            conexao.execute(text(sql))

    command.upgrade(config, "head")
    with engine.connect() as conexao:
        via_do_tempo = conexao.execute(text("SELECT via_id FROM tempos_semaforicos")).scalar()
        origem = conexao.execute(text("SELECT origem FROM ciclos_semaforicos")).scalar()
    assert via_do_tempo == 5  # preenchida a partir do semáforo
    assert origem == "manual"
