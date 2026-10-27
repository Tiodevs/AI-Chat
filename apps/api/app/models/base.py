"""Base declarativa das entidades. Seção 8 do SDD."""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

_NAMING_CONVENTION = {
    "pk": "%(table_name)s_pkey",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "%(constraint_name)s",
    "ix": "%(table_name)s_%(column_0_name)s_idx",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=_NAMING_CONVENTION)
