"""O modelo de chunks segue a seção 8.1 do SDD."""

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
