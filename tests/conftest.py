"""Configuração dos testes: banco SQLite em memória isolado por teste e usuários de exemplo."""

import os

os.environ.update(
    {
        "GSA_DATABASE_URL": "sqlite://",
        "GSA_JWT_SEGREDO": "segredo-usado-somente-nos-testes-automatizados",
        "GSA_CHAVE_API_DETECCAO": "chave-de-teste",
        "GSA_HASH_ITERACOES": "1000",
        "GSA_INTERVALO_VERIFICACAO_FALHAS": "0",
    }
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import criar_engine, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import PerfilUsuario  # noqa: E402
from app.schemas.usuario import UsuarioCreate  # noqa: E402
from app.services.usuario_service import UsuarioService  # noqa: E402

CHAVE_DETECCAO = {"X-API-Key": "chave-de-teste"}
SENHA = "senha-segura-123"


# Por padrão os testes usam SQLite em memória; defina GSA_TESTE_DATABASE_URL para rodar a
# mesma suíte em um PostgreSQL vazio (como faz a integração contínua).
URL_TESTE = os.environ.get("GSA_TESTE_DATABASE_URL", "sqlite://")


@pytest.fixture
def fabrica_sessao():
    engine = criar_engine(URL_TESTE)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db(fabrica_sessao):
    with fabrica_sessao() as sessao:
        yield sessao


@pytest.fixture
def client(fabrica_sessao):
    def _get_db():
        sessao = fabrica_sessao()
        try:
            yield sessao
        finally:
            sessao.close()

    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as cliente:
        yield cliente
    app.dependency_overrides.clear()


def _criar_usuario_e_entrar(client, db, email: str, perfil: PerfilUsuario) -> dict[str, str]:
    UsuarioService(db).criar(
        UsuarioCreate(nome=perfil.value, email=email, senha=SENHA, perfil=perfil)
    )
    resposta = client.post("/auth/login", data={"username": email, "password": SENHA})
    assert resposta.status_code == 200, resposta.text
    return {"Authorization": f"Bearer {resposta.json()['access_token']}"}


@pytest.fixture
def admin(client, db):
    return _criar_usuario_e_entrar(client, db, "admin@teste.local", PerfilUsuario.ADMINISTRADOR)


@pytest.fixture
def operador(client, db):
    return _criar_usuario_e_entrar(client, db, "operador@teste.local", PerfilUsuario.OPERADOR)


@pytest.fixture
def deteccao():
    return dict(CHAVE_DETECCAO)


@pytest.fixture
def cruzamento(client, admin):
    """Cruzamento do exemplo do documento de requisitos: 2 vias, verde 20–70 s, ciclo de 90 s."""
    resposta = client.post(
        "/cruzamentos",
        json={"nome": "Cruzamento de teste", "latitude": -1.45, "longitude": -48.49},
        headers=admin,
    )
    assert resposta.status_code == 201, resposta.text
    cruzamento_id = resposta.json()["id"]
    vias = []
    for nome, direcao, faixas in (("Via A", "norte", 2), ("Via B", "leste", 1)):
        via = client.post(
            f"/cruzamentos/{cruzamento_id}/vias",
            json={"nome": nome, "direcao": direcao, "quantidadeFaixas": faixas},
            headers=admin,
        ).json()
        semaforo = client.post(
            f"/vias/{via['id']}/semaforo",
            json={
                "tempoMinimoVerde": 20,
                "tempoMaximoVerde": 70,
                "tempoAmarelo": 3,
                "tempoVermelho": 2,
            },
            headers=admin,
        )
        assert semaforo.status_code == 201, semaforo.text
        vias.append(via["id"])
    return {"id": cruzamento_id, "vias": vias}


def lote(cruzamento: dict, *quantidades: int) -> dict:
    return {
        "cruzamentoId": cruzamento["id"],
        "leituras": [
            {"viaId": via_id, "quantidadeVeiculos": qtd}
            for via_id, qtd in zip(cruzamento["vias"], quantidades, strict=True)
        ],
    }
