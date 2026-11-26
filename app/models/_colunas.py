from enum import StrEnum

from sqlalchemy import Enum


def coluna_enum(enum_cls: type[StrEnum]) -> Enum:
    """Enum salvo como texto (valor em minúsculas), portável entre SQLite e PostgreSQL."""
    return Enum(
        enum_cls,
        native_enum=False,
        length=20,
        values_callable=lambda membros: [m.value for m in membros],
        validate_strings=True,
    )
