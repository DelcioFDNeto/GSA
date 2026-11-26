"""Dependências compartilhadas pelas rotas: sessão do banco e autenticação (RNF07)."""

from typing import Annotated

from fastapi import Depends
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AcessoNegado, NaoAutenticado
from app.core.seguranca import chaves_iguais, decodificar_token
from app.db.session import get_db
from app.models import PerfilUsuario, Usuario
from app.repositories.usuario_repository import UsuarioRepository

DbSession = Annotated[Session, Depends(get_db)]

esquema_oauth2 = OAuth2PasswordBearer(
    tokenUrl="auth/login",
    auto_error=False,
    description="Login com e-mail e senha (perfis administrador e operador).",
)
esquema_chave_api = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    description="Chave do sistema de detecção de veículos, usada no envio de leituras.",
)


def usuario_opcional(
    db: DbSession, token: Annotated[str | None, Depends(esquema_oauth2)]
) -> Usuario | None:
    if not token:
        return None
    payload = decodificar_token(token)
    if payload is None:
        raise NaoAutenticado("Token inválido ou expirado")
    usuario = UsuarioRepository(db).obter(int(payload["sub"]))
    if usuario is None or not usuario.ativo:
        raise NaoAutenticado("Usuário do token não existe ou está inativo")
    return usuario


def usuario_logado(usuario: Annotated[Usuario | None, Depends(usuario_opcional)]) -> Usuario:
    if usuario is None:
        raise NaoAutenticado("Faça login em POST /auth/login e envie o token Bearer")
    return usuario


def exigir_perfis(*perfis: PerfilUsuario):
    nomes = ", ".join(p.value for p in perfis)

    def verificar(usuario: Annotated[Usuario, Depends(usuario_logado)]) -> Usuario:
        if usuario.perfil not in perfis:
            raise AcessoNegado(f"Operação permitida apenas para o perfil: {nomes}")
        return usuario

    return verificar


def autorizar_deteccao(
    chave: Annotated[str | None, Depends(esquema_chave_api)],
    usuario: Annotated[Usuario | None, Depends(usuario_opcional)],
) -> None:
    """Envio de leituras: chave do sistema de detecção ou token de um usuário logado."""
    if chave is not None:
        esperada = get_settings().chave_api_deteccao
        if esperada and chaves_iguais(chave, esperada):
            return
        raise NaoAutenticado("Chave de API inválida")
    if usuario is None:
        raise NaoAutenticado("Envie a chave do sistema de detecção (X-API-Key) ou um token Bearer")


ApenasAdministrador = Depends(exigir_perfis(PerfilUsuario.ADMINISTRADOR))
AdministradorOuOperador = Depends(
    exigir_perfis(PerfilUsuario.ADMINISTRADOR, PerfilUsuario.OPERADOR)
)
SistemaDeteccao = Depends(autorizar_deteccao)
UsuarioLogado = Annotated[Usuario, Depends(usuario_logado)]
