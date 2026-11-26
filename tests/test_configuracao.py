import pytest

from app.core.config import Settings


@pytest.mark.parametrize(
    ("informada", "esperada"),
    [
        ("postgres://u:s@h:5432/gsa", "postgresql+psycopg://u:s@h:5432/gsa"),
        ("postgresql://u:s@h/gsa", "postgresql+psycopg://u:s@h/gsa"),
        ("postgresql+psycopg://u:s@h/gsa", "postgresql+psycopg://u:s@h/gsa"),
        ("sqlite:///./gsa.db", "sqlite:///./gsa.db"),
    ],
)
def test_url_do_banco_usa_driver_psycopg(informada, esperada):
    assert Settings(database_url=informada, _env_file=None).database_url == esperada
