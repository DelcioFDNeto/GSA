"""Configurações da aplicação, lidas de variáveis de ambiente (prefixo GSA_) ou do arquivo .env."""

from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="GSA_", extra="ignore")

    nome_aplicacao: str = "Gestão Semafórica Adaptativa"
    versao: str = "1.2.0"
    database_url: str = "sqlite:///./gsa.db"

    # Valores iniciais dos parâmetros do algoritmo. Depois de criados no banco,
    # passam a ser alterados pela API (PUT /parametros — RF16).
    duracao_ciclo_padrao: int = 90
    limite_fluxo_baixo: float = 5
    limite_fluxo_moderado: float = 15
    limite_fluxo_alto: float = 25
    verde_minimo_padrao: int = 15
    verde_maximo_padrao: int = 60
    tempo_maximo_sem_leitura: int = 300  # segundos sem leitura até registrar falha (RF18)
    # Regra de Webster: fluxo de saturação (veíc/h por faixa), intervalo coberto por cada contagem
    # e limites do ciclo calculado, em segundos
    fluxo_saturacao_por_faixa: int = 1800
    intervalo_contagem: int = 90
    ciclo_minimo: int = 40
    ciclo_maximo: int = 150

    # Verificação periódica de falhas, em segundos (0 desativa)
    intervalo_verificacao_falhas: int = 60

    # Segurança (RNF07)
    jwt_segredo: str | None = None  # sem valor, um segredo aleatório é gerado a cada início
    jwt_expiracao_minutos: int = 60
    chave_api_deteccao: str | None = None  # chave do sistema de detecção (cabeçalho X-API-Key)
    hash_iteracoes: int = 600_000  # PBKDF2-SHA256

    @field_validator("database_url")
    @classmethod
    def usar_driver_psycopg(cls, url: str) -> str:
        """Provedores de nuvem entregam a URL como postgres:// ou postgresql://; a API usa o
        driver psycopg 3, que o SQLAlchemy só escolhe com o prefixo postgresql+psycopg://."""
        for prefixo in ("postgres://", "postgresql://"):
            if url.startswith(prefixo):
                return "postgresql+psycopg://" + url.removeprefix(prefixo)
        return url

    @model_validator(mode="after")
    def validar_parametros(self) -> "Settings":
        if self.duracao_ciclo_padrao <= 0:
            raise ValueError("GSA_DURACAO_CICLO_PADRAO deve ser maior que zero")
        if not 0 < self.limite_fluxo_baixo < self.limite_fluxo_moderado < self.limite_fluxo_alto:
            raise ValueError("Limites de fluxo devem ser positivos e crescentes")
        if not 0 < self.verde_minimo_padrao <= self.verde_maximo_padrao:
            raise ValueError("Verde mínimo padrão deve ser positivo e menor ou igual ao máximo")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
