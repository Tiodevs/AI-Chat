"""Tabela `chunks`: pedaços do texto de uma versão, com vetor e texto pesquisável.

Camada de entidade de persistência (seção 6.2 do SDD). `DocumentRepository.publish` grava e
ativa os chunks, e `RetrievalRepository` faz a busca híbrida sobre eles. A migração
`0002_corpus` e os testes importam `CHUNK_TSV_EXPRESSION`. Seções 8.1, 8.2 e 8.4 do SDD.
"""

import uuid

from sqlalchemy import Boolean, Computed, ForeignKey, Index, Integer, Text, Uuid, text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.vector import EMBEDDING_DIMENSIONS, Vector

# Expressão da coluna gerada `tsv` (seção 8.1). `to_tsvector('portuguese', ...)` quebra o texto
# em lexemas com o dicionário português, que tira palavras vazias e reduz as palavras ao
# radical. O título de seção entra junto, e o `coalesce` evita que um título nulo anule tudo.
CHUNK_TSV_EXPRESSION = "to_tsvector('portuguese', coalesce(heading, '') || ' ' || content)"


class Chunk(Base):
    """Um pedaço de até 1.000 caracteres de uma versão, pronto para a busca (seção 7.3).

    Um chunk é pesquisável quando o documento está `active`, a versão dele é a
    `active_version` do documento e `active` é verdadeiro (seção 8.2). Os chunks antigos não
    são apagados: publicar uma versão nova só os desativa.
    """

    __tablename__ = "chunks"
    __table_args__ = (
        # Índice HNSW do pgvector, aproximado, para a busca por vizinho mais próximo.
        # `vector_cosine_ops` faz o índice servir ao operador de distância de cosseno `<=>`. O
        # `WHERE active` deixa só os chunks ativos dentro do índice (seção 8.2).
        Index(
            "chunks_embedding_idx",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_where=text("active"),
        ),
        # Índice GIN, invertido por lexema, para o `tsv @@ consulta` da busca por palavra.
        # Também parcial em `active`.
        Index(
            "chunks_tsv_idx",
            "tsv",
            postgresql_using="gin",
            postgresql_where=text("active"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    # Sem `ondelete` e sem índice próprio: chunks e versões não são apagados.
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_versions.id"),
        nullable=False,
    )
    # Posição do chunk no documento, a partir de 0.
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    # Título Markdown da seção de onde o chunk saiu. Nulo quando não há título.
    heading: Mapped[str | None] = mapped_column(Text, nullable=True)
    # O texto do chunk, sem o prefixo de embedding da seção 8.3.
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # `vector(768)`. O vetor é gravado como veio do modelo de embedding (seção 8.3).
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=False)
    # `TSVECTOR` é o tipo de texto pesquisável do PostgreSQL. `Computed(..., persisted=True)`
    # declara uma coluna `GENERATED ALWAYS AS (...) STORED`: o banco calcula e guarda o valor a
    # cada INSERT e UPDATE, e o código nunca escreve nela.
    tsv: Mapped[str] = mapped_column(
        TSVECTOR(),
        Computed(CHUNK_TSV_EXPRESSION, persisted=True),
        nullable=False,
    )
    # Entra `false` e vira `true` na transação que publica a versão (seção 7.3).
    active: Mapped[bool] = mapped_column(Boolean, nullable=False)
