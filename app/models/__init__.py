"""Importa todos os modelos para registrá-los no metadata (usado pelo Alembic)."""

from app.models.ciclo import CicloSemaforico, TempoSemaforico
from app.models.cruzamento import Cruzamento
from app.models.enums import (
    Direcao,
    ModoOperacao,
    OrigemCiclo,
    PerfilUsuario,
    RegraTemporizacao,
    StatusCruzamento,
    StatusFalha,
    StatusSemaforo,
    TipoFalha,
)
from app.models.falha import Falha
from app.models.leitura import LeituraTrafego
from app.models.parametros import ParametrosAlgoritmo
from app.models.semaforo import Semaforo
from app.models.usuario import Usuario
from app.models.via import Via

__all__ = [
    "CicloSemaforico",
    "Cruzamento",
    "Direcao",
    "Falha",
    "LeituraTrafego",
    "ModoOperacao",
    "OrigemCiclo",
    "ParametrosAlgoritmo",
    "PerfilUsuario",
    "RegraTemporizacao",
    "Semaforo",
    "StatusCruzamento",
    "StatusFalha",
    "StatusSemaforo",
    "TempoSemaforico",
    "TipoFalha",
    "Usuario",
    "Via",
]
