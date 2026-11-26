from app.core.seguranca import criar_token, decodificar_token, gerar_hash_senha, verificar_senha


def test_hash_de_senha_confere_e_usa_sal():
    primeiro = gerar_hash_senha("minha-senha", iteracoes=1000)
    segundo = gerar_hash_senha("minha-senha", iteracoes=1000)
    assert primeiro != segundo  # sal aleatório
    assert verificar_senha("minha-senha", primeiro)
    assert not verificar_senha("outra-senha", primeiro)
    assert not verificar_senha("minha-senha", "formato-invalido")


def test_token_valido_e_adulterado():
    token, validade = criar_token(7, "operador")
    assert validade > 0
    assert decodificar_token(token)["sub"] == "7"
    assert decodificar_token(token[:-2] + "xx") is None
