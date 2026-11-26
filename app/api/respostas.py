from typing import Any

from app.schemas.base import ErroResposta

# Respostas de erro documentadas no Swagger (RNF05 / RNF06)
ERROS_PADRAO: dict[int | str, dict[str, Any]] = {
    400: {"model": ErroResposta, "description": "Dados inválidos ou regra de negócio violada"},
    404: {"model": ErroResposta, "description": "Recurso não encontrado"},
    500: {"model": ErroResposta, "description": "Erro interno do servidor"},
}

# Acrescentadas às rotas protegidas por autenticação (RNF07)
ERROS_AUTENTICACAO: dict[int | str, dict[str, Any]] = {
    401: {
        "model": ErroResposta,
        "description": "Não autenticado (token ou chave ausente/inválido)",
    },
    403: {"model": ErroResposta, "description": "Perfil sem permissão para a operação"},
}
