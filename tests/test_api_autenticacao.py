"""RNF07 — autenticação e perfis de acesso."""

NOVO_CRUZAMENTO = {"nome": "X", "latitude": 0, "longitude": 0}


def test_login_retorna_token_bearer(client, admin):
    resposta = client.get("/auth/me", headers=admin)
    assert resposta.status_code == 200
    assert resposta.json()["perfil"] == "administrador"


def test_login_com_senha_errada_retorna_401(client, admin):
    resposta = client.post(
        "/auth/login", data={"username": "admin@teste.local", "password": "errada!!"}
    )
    assert resposta.status_code == 401
    assert resposta.headers["www-authenticate"] == "Bearer"
    assert resposta.json()["mensagem"] == "E-mail ou senha inválidos"


def test_login_com_email_inexistente_retorna_401(client):
    resposta = client.post("/auth/login", data={"username": "ninguem@x.com", "password": "abc"})
    assert resposta.status_code == 401


def test_operacao_administrativa_sem_token_retorna_401(client):
    assert client.post("/cruzamentos", json=NOVO_CRUZAMENTO).status_code == 401


def test_token_invalido_retorna_401(client):
    resposta = client.post(
        "/cruzamentos", json=NOVO_CRUZAMENTO, headers={"Authorization": "Bearer abc.def.ghi"}
    )
    assert resposta.status_code == 401
    assert resposta.json()["mensagem"] == "Token inválido ou expirado"


def test_operador_nao_pode_cadastrar(client, operador):
    resposta = client.post("/cruzamentos", json=NOVO_CRUZAMENTO, headers=operador)
    assert resposta.status_code == 403
    assert resposta.json()["erro"] == "Acesso negado"


def test_consultas_sao_publicas(client, cruzamento):
    assert client.get("/cruzamentos").status_code == 200
    assert client.get(f"/cruzamentos/{cruzamento['id']}/situacao").status_code == 200


def test_admin_cadastra_e_lista_usuarios(client, admin):
    novo = {"nome": "Ana", "email": "ana@gsa.local", "senha": "12345678", "perfil": "operador"}
    criado = client.post("/usuarios", json=novo, headers=admin)
    assert criado.status_code == 201
    assert "senha" not in criado.json() and "senhaHash" not in criado.json()

    repetido = client.post("/usuarios", json=novo | {"email": "ANA@gsa.local"}, headers=admin)
    assert repetido.status_code == 400

    emails = [u["email"] for u in client.get("/usuarios", headers=admin).json()]
    assert "ana@gsa.local" in emails


def test_usuario_com_senha_curta_e_rejeitado(client, admin):
    dados = {"nome": "Bia", "email": "bia@gsa.local", "senha": "123", "perfil": "operador"}
    assert client.post("/usuarios", json=dados, headers=admin).status_code == 400


def test_operador_nao_lista_usuarios(client, operador):
    assert client.get("/usuarios", headers=operador).status_code == 403
