from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Usuario


class UsuarioRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def adicionar(self, usuario: Usuario) -> Usuario:
        self.db.add(usuario)
        self.db.commit()
        self.db.refresh(usuario)
        return usuario

    def obter(self, usuario_id: int) -> Usuario | None:
        return self.db.get(Usuario, usuario_id)

    def obter_por_email(self, email: str) -> Usuario | None:
        consulta = select(Usuario).where(func.lower(Usuario.email) == email.lower())
        return self.db.scalars(consulta).first()

    def listar(self) -> list[Usuario]:
        return list(self.db.scalars(select(Usuario).order_by(Usuario.id)))
