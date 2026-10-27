"""Coluna vector(768). Seção 8.1 do SDD."""

from typing import Any

from sqlalchemy.types import UserDefinedType

EMBEDDING_DIMENSIONS = 768


class Vector(UserDefinedType[list[float]]):
    cache_ok = True

    def __init__(self, dimensions: int) -> None:
        super().__init__()
        self.dimensions = dimensions

    def get_col_spec(self, **kw: Any) -> str:
        return f"vector({self.dimensions})"
