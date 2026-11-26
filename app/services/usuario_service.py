"""RNF07 — usuários e autenticação."""

from sqlalchemy.orm import Session

from app.core.exceptions import NaoAutenticado, RegraDeNegocioViolada
from app.core.seguranca import criar_token, gerar_hash_senha, verificar_senha
from app.models import Usuario
from app.repositories.usuario_repository import UsuarioRepository
from app.schemas.usuario import TokenRead, UsuarioCreate

# Hash calculado uma vez para igualar o tempo de resposta quando o e-mail não existe
_HASH_FICTICIO: str | None = None


class UsuarioService:
    def __init__(self, db: Session) -> None:
        self.repo = UsuarioRepository(db)

    def criar(self, dados: UsuarioCreate) -> Usuario:
        if self.repo.obter_por_email(dados.email) is not None:
            raise RegraDeNegocioViolada(f"Já existe usuário com o e-mail {dados.email}")
        return self.repo.adicionar(
            Usuario(
                nome=dados.nome,
                email=dados.email.lower(),
                senha_hash=gerar_hash_senha(dados.senha),
                perfil=dados.perfil,
            )
        )

    def listar(self) -> list[Usuario]:
        return self.repo.listar()

    def autenticar(self, email: str, senha: str) -> TokenRead:
        global _HASH_FICTICIO
        usuario = self.repo.obter_por_email(email)
        if usuario is None:
            _HASH_FICTICIO = _HASH_FICTICIO or gerar_hash_senha("senha-inexistente")
            verificar_senha(senha, _HASH_FICTICIO)
            raise NaoAutenticado("E-mail ou senha inválidos")
        if not verificar_senha(senha, usuario.senha_hash) or not usuario.ativo:
            raise NaoAutenticado("E-mail ou senha inválidos")
        token, validade = criar_token(usuario.id, usuario.perfil.value)
        return TokenRead(access_token=token, expires_in=validade)
