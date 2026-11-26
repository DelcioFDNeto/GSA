from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import ApenasAdministrador, DbSession, UsuarioLogado
from app.api.respostas import ERROS_AUTENTICACAO, ERROS_PADRAO
from app.schemas.usuario import TokenRead, UsuarioCreate, UsuarioRead
from app.services.usuario_service import UsuarioService

router = APIRouter(tags=["Autenticação"], responses=ERROS_PADRAO)


@router.post(
    "/auth/login",
    response_model=TokenRead,
    summary="Entrar (obter token)",
    responses=ERROS_AUTENTICACAO,
)
def login(dados: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession):
    """RNF07 — formulário OAuth2: `username` é o e-mail. O token vale pelo tempo configurado
    em GSA_JWT_EXPIRACAO_MINUTOS."""
    return UsuarioService(db).autenticar(dados.username, dados.password)


@router.get(
    "/auth/me", response_model=UsuarioRead, summary="Usuário logado", responses=ERROS_AUTENTICACAO
)
def usuario_atual(usuario: UsuarioLogado):
    return usuario


@router.post(
    "/usuarios",
    response_model=UsuarioRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar usuário",
    dependencies=[ApenasAdministrador],
    responses=ERROS_AUTENTICACAO,
)
def criar_usuario(dados: UsuarioCreate, db: DbSession):
    """Cadastra administrador ou operador. Perfil administrador."""
    return UsuarioService(db).criar(dados)


@router.get(
    "/usuarios",
    response_model=list[UsuarioRead],
    summary="Listar usuários",
    dependencies=[ApenasAdministrador],
    responses=ERROS_AUTENTICACAO,
)
def listar_usuarios(db: DbSession):
    return UsuarioService(db).listar()
