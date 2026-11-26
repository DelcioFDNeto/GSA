"""Cria um usuário (por exemplo, o primeiro administrador de um banco novo).

Uso: python -m scripts.criar_usuario --nome "Maria" --email maria@exemplo.com --perfil administrador
A senha é pedida no terminal (ou lida de GSA_NOVA_SENHA, para automação).
"""

import argparse
import getpass
import os

from app.core.exceptions import ErroDominio
from app.db.session import SessionLocal
from app.models import PerfilUsuario
from app.schemas.usuario import UsuarioCreate
from app.services.usuario_service import UsuarioService


def main() -> None:
    parser = argparse.ArgumentParser(description="Cria um usuário da API")
    parser.add_argument("--nome", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument(
        "--perfil", choices=[p.value for p in PerfilUsuario], default=PerfilUsuario.ADMINISTRADOR
    )
    args = parser.parse_args()

    senha = os.environ.get("GSA_NOVA_SENHA") or getpass.getpass("Senha (mínimo 8 caracteres): ")
    try:
        dados = UsuarioCreate(nome=args.nome, email=args.email, senha=senha, perfil=args.perfil)
        with SessionLocal() as db:
            usuario = UsuarioService(db).criar(dados)
    except ErroDominio as erro:
        raise SystemExit(erro.mensagem) from erro
    except ValueError as erro:  # validação do Pydantic
        raise SystemExit(str(erro)) from erro
    print(f"Usuário {usuario.id} criado: {usuario.email} ({usuario.perfil.value})")


if __name__ == "__main__":
    main()
