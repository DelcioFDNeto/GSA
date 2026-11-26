from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import PerfilUsuario
from app.schemas.base import SchemaBase

PADRAO_EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class UsuarioCreate(SchemaBase):
    nome: str = Field(min_length=2, max_length=120)
    email: str = Field(max_length=254, pattern=PADRAO_EMAIL, examples=["operador@gsa.local"])
    senha: str = Field(min_length=8, max_length=128)
    perfil: PerfilUsuario


class UsuarioRead(SchemaBase):
    id: int
    nome: str
    email: str
    perfil: PerfilUsuario
    ativo: bool
    criado_em: datetime


class TokenRead(BaseModel):
    """Formato OAuth2 (snake_case), exigido pelo botão Authorize do Swagger."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
