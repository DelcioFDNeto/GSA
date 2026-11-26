"""Hash de senhas (PBKDF2-SHA256, biblioteca padrão) e tokens JWT (RNF07)."""

import base64
import hashlib
import hmac
import logging
import secrets
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import jwt

from app.core.config import get_settings

logger = logging.getLogger("gsa")
ALGORITMO_JWT = "HS256"
_PREFIXO_HASH = "pbkdf2_sha256"


def gerar_hash_senha(senha: str, iteracoes: int | None = None) -> str:
    iteracoes = iteracoes or get_settings().hash_iteracoes
    sal = secrets.token_bytes(16)
    derivada = hashlib.pbkdf2_hmac("sha256", senha.encode(), sal, iteracoes)
    return "$".join([_PREFIXO_HASH, str(iteracoes), _b64(sal), _b64(derivada)])


def verificar_senha(senha: str, senha_hash: str) -> bool:
    try:
        prefixo, iteracoes, sal, esperado = senha_hash.split("$")
    except ValueError:
        return False
    if prefixo != _PREFIXO_HASH:
        return False
    derivada = hashlib.pbkdf2_hmac("sha256", senha.encode(), _de_b64(sal), int(iteracoes))
    return hmac.compare_digest(derivada, _de_b64(esperado))


@lru_cache
def segredo_jwt() -> str:
    segredo = get_settings().jwt_segredo
    if not segredo:
        logger.warning(
            "GSA_JWT_SEGREDO não definido: usando segredo aleatório; "
            "os tokens deixam de valer quando a API reiniciar."
        )
        segredo = secrets.token_urlsafe(48)
    return segredo


def criar_token(usuario_id: int, perfil: str) -> tuple[str, int]:
    """Retorna o token e sua validade em segundos."""
    minutos = get_settings().jwt_expiracao_minutos
    agora = datetime.now(UTC)
    payload = {
        "sub": str(usuario_id),
        "perfil": perfil,
        "iat": agora,
        "exp": agora + timedelta(minutes=minutos),
    }
    return jwt.encode(payload, segredo_jwt(), algorithm=ALGORITMO_JWT), minutos * 60


def decodificar_token(token: str) -> dict | None:
    try:
        return jwt.decode(
            token, segredo_jwt(), algorithms=[ALGORITMO_JWT], options={"require": ["exp", "sub"]}
        )
    except jwt.PyJWTError:
        return None


def chaves_iguais(recebida: str, esperada: str) -> bool:
    return hmac.compare_digest(recebida.encode(), esperada.encode())


def _b64(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).decode().rstrip("=")


def _de_b64(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))
