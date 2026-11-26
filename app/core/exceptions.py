"""Exceções de domínio. São convertidas em respostas HTTP pelos handlers em app.main."""


class ErroDominio(Exception):
    status_code = 400
    titulo = "Requisição inválida"
    cabecalhos: dict[str, str] | None = None

    def __init__(self, mensagem: str, detalhes: list[str] | None = None) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.detalhes = detalhes


class RecursoNaoEncontrado(ErroDominio):
    status_code = 404
    titulo = "Recurso não encontrado"

    def __init__(self, recurso: str, identificador: int) -> None:
        super().__init__(f"{recurso} {identificador} não existe")


class RegraDeNegocioViolada(ErroDominio):
    status_code = 400
    titulo = "Regra de negócio violada"


class NaoAutenticado(ErroDominio):
    status_code = 401
    titulo = "Não autenticado"
    cabecalhos = {"WWW-Authenticate": "Bearer"}


class AcessoNegado(ErroDominio):
    status_code = 403
    titulo = "Acesso negado"
