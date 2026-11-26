from enum import StrEnum


class StatusCruzamento(StrEnum):
    ATIVO = "ativo"
    INATIVO = "inativo"


class StatusSemaforo(StrEnum):
    ATIVO = "ativo"
    INATIVO = "inativo"
    MANUTENCAO = "manutencao"


class Direcao(StrEnum):
    NORTE = "norte"
    SUL = "sul"
    LESTE = "leste"
    OESTE = "oeste"
    NORDESTE = "nordeste"
    NOROESTE = "noroeste"
    SUDESTE = "sudeste"
    SUDOESTE = "sudoeste"


class OrigemCiclo(StrEnum):
    AUTOMATICO = "automatico"  # gerado após um lote de leituras (RF12)
    MANUAL = "manual"  # solicitado pelo operador


class TipoFalha(StrEnum):
    SEM_LEITURA = "sem_leitura"  # ausência prolongada de leitura da via
    CALCULO_INDISPONIVEL = "calculo_indisponivel"  # cruzamento sem semáforo ativo para calcular
    MANUAL = "manual"  # registrada pelo operador


class StatusFalha(StrEnum):
    ABERTA = "aberta"
    RESOLVIDA = "resolvida"


class PerfilUsuario(StrEnum):
    ADMINISTRADOR = "administrador"
    OPERADOR = "operador"


class RegraTemporizacao(StrEnum):
    PROPORCIONAL = "proporcional"  # ciclo fixo, verde proporcional aos veículos
    WEBSTER = "webster"  # ciclo ótimo de Webster, varia com a demanda


class ModoOperacao(StrEnum):
    ADAPTATIVO = "adaptativo"
    CONTINGENCIA = "contingencia"  # faltam leituras recentes: plano fixo
