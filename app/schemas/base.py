from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class SchemaBase(BaseModel):
    """JSON em camelCase (ex.: cruzamentoId), código Python em snake_case.

    As respostas da API saem em camelCase porque o FastAPI serializa pelo alias.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        from_attributes=True,
    )


class ErroResposta(SchemaBase):
    status: int
    erro: str
    mensagem: str
    detalhes: list[str] | None = None
