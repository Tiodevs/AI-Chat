"""O modelo `Chunk` segue a seção 8.1 do SDD: vetor de 768 dimensões e `tsv` em português.

Lê só os metadados da tabela no SQLAlchemy, sem banco nem rede: o tipo `Vector` com
`EMBEDDING_DIMENSIONS` (seção 8.3), o `heading` anulável e a coluna gerada com
`CHUNK_TSV_EXPRESSION`, a mesma expressão que a migração `0002_corpus` usa. A coluna criada no
PostgreSQL é conferida em `tests/integration/test_corpus_schema.py`.
"""

from app.models import Chunk
from app.models.chunk import CHUNK_TSV_EXPRESSION
from app.models.vector import EMBEDDING_DIMENSIONS, Vector


def test_chunk_embedding_is_768_and_tsv_uses_portuguese() -> None:
    embedding = Chunk.__table__.c.embedding
    assert isinstance(embedding.type, Vector)
    assert embedding.type.dimensions == EMBEDDING_DIMENSIONS == 768
    assert Chunk.__table__.c.heading.nullable is True
    generated = Chunk.__table__.c.tsv.computed
    assert generated is not None
    assert str(generated.sqltext) == CHUNK_TSV_EXPRESSION
