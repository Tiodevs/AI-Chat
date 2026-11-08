"""Base declarativa de todas as entidades SQLAlchemy da API.

Camada de entidade de persistência (seção 6.2 do SDD). Todo modelo de `app.models` herda de
`Base`. O `alembic/env.py` usa `Base.metadata` como o esquema esperado, e o teste de esquema
confere que o banco migrado tem as mesmas colunas. Seção 8 do SDD.

No SQLAlchemy 2, cada coluna é um atributo `Mapped[tipo]`, que diz o tipo Python devolvido,
com `mapped_column(...)`, que diz o tipo SQL, a nulabilidade e os padrões.
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Os padrões de nome que o próprio PostgreSQL usa: `users_pkey`, `users_email_key`,
# `<tabela>_<coluna>_fkey` e `<tabela>_<coluna>_idx`. Uma restrição declarada sem nome, como
# `unique=True` ou `ForeignKey("users.id")`, ganha no modelo o mesmo nome que as migrações
# gravaram no banco. `ck` mantém o nome explícito de cada `CheckConstraint`.
_NAMING_CONVENTION = {
    "pk": "%(table_name)s_pkey",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "%(constraint_name)s",
    "ix": "%(table_name)s_%(column_0_name)s_idx",
}


class Base(DeclarativeBase):
    """Classe mãe das entidades. O `metadata` reúne as tabelas com a convenção de nomes."""

    metadata = MetaData(naming_convention=_NAMING_CONVENTION)
