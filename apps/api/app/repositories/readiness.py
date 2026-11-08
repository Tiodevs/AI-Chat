"""Consulta de prontidão: banco, extensão vector e dimensão. NFR-9.

Camada de repositório (seção 6.2 do SDD). Lê só os catálogos do PostgreSQL. Quem usa é o
`ReadinessService`, que o `GET /ready` chama numa conexão nova, fora do pool (seção 6.4).
Seção 8.3 do SDD.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class ReadinessRepository:
    """As três conferências do `/ready`: o banco responde, o pgvector existe e a dimensão."""

    def __init__(self, session: AsyncSession) -> None:
        """Usa a sessão aberta pelo serviço, sem abrir transação própria."""
        self._session = session

    async def ping(self) -> None:
        """`SELECT 1`. Levanta erro se o banco não responde."""
        await self._session.execute(text("SELECT 1"))

    async def vector_extension_installed(self) -> bool:
        """Diz se a extensão `vector` está instalada, pelo catálogo `pg_extension`."""
        result = await self._session.execute(
            text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
        )
        return bool(result.scalar_one())

    async def embedding_column_type(self) -> str | None:
        """Tipo real de `chunks.embedding`, como `vector(768)`, ou `None` sem a coluna.

        `pg_attribute` lista as colunas, `pg_class` as tabelas e `pg_namespace` os esquemas.
        `format_type` escreve o tipo com o modificador, que no pgvector é a dimensão.
        `attisdropped` descarta coluna apagada que ainda conste no catálogo. O serviço compara
        o resultado com `EMBEDDING_DIMENSIONS`.
        """
        result = await self._session.scalar(
            text(
                "SELECT format_type(attribute.atttypid, attribute.atttypmod) "
                "FROM pg_attribute AS attribute "
                "JOIN pg_class AS table_name ON table_name.oid = attribute.attrelid "
                "JOIN pg_namespace AS namespace ON namespace.oid = table_name.relnamespace "
                "WHERE namespace.nspname = 'public' "
                "AND table_name.relname = 'chunks' "
                "AND attribute.attname = 'embedding' "
                "AND NOT attribute.attisdropped"
            )
        )
        if result is None:
            return None
        return str(result)
