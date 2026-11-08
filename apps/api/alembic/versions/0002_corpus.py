"""Tabelas do corpus e os índices da seção 8.2 que elas suportam.

Revision ID: 0002_corpus
Revises: 0001_initial
Create Date: 2026-10-27

Os B-tree de messages, conversations, consent_records e data_subject_requests
entram junto com essas tabelas. Seções 8.1 e 8.2 do SDD.

Cria o corpus da seção 8.1:

- `documents`: título, `slug` único, `status` (`active` ou `archived`) e `active_version`,
  a versão que a busca usa. `created_by` aponta para `users` sem `ondelete`, então um
  usuário que criou documento não pode ser apagado; a semente grava o admin mais antigo.
- `document_versions`: uma linha por versão, única em `(document_id, version)`, com os bytes
  originais, o checksum e o status da ingestão (`processing`, `ready` ou `failed`).
- `chunks`: o texto, o `embedding vector(768)` e o `tsv`, coluna gerada e armazenada com o
  `to_tsvector('portuguese', ...)` da seção 8.1.

`documents.active_version` e `document_versions.document_id` apontam um para o outro, então a
chave de `active_version` só entra depois das duas tabelas. Os índices HNSW, com distância de
cosseno, e GIN são parciais (`WHERE active`): cobrem só os chunks que a busca pode devolver
(seção 8.2).

A dimensão e a expressão do `tsv` vêm do código atual (`app.models.vector` e
`app.models.chunk`): um banco criado do zero recebe o valor de hoje. Mudar a dimensão pede
uma revisão nova e um re-embedding completo (seção 8.3), não a edição da constante. O
downgrade apaga as três tabelas, com a chave circular solta antes.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import TSVECTOR

from app.models.chunk import CHUNK_TSV_EXPRESSION
from app.models.vector import EMBEDDING_DIMENSIONS, Vector

revision: str = "0002_corpus"
down_revision: str | Sequence[str] | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria `documents`, `document_versions` e `chunks`, com os índices da busca."""
    # `active_version` nasce sem chave: a tabela de versões ainda não existe.
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("active_version", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("status IN ('active', 'archived')", name="documents_status"),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="documents_created_by_fkey",
        ),
        sa.PrimaryKeyConstraint("id", name="documents_pkey"),
        sa.UniqueConstraint("slug", name="documents_slug_key"),
    )
    op.create_table(
        "document_versions",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("media_type", sa.Text(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("original_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("ingestion_status", sa.Text(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "ingestion_status IN ('processing', 'ready', 'failed')",
            name="document_versions_ingestion_status",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="document_versions_document_id_fkey",
        ),
        sa.PrimaryKeyConstraint("id", name="document_versions_pkey"),
        sa.UniqueConstraint(
            "document_id",
            "version",
            name="document_versions_document_id_version_key",
        ),
    )
    # B-tree da seção 8.2. A restrição única de `(document_id, version)` já começa pela mesma
    # coluna.
    op.create_index(
        "document_versions_document_id_idx",
        "document_versions",
        ["document_id"],
        unique=False,
    )
    # A chave circular entra agora, com as duas tabelas criadas.
    op.create_foreign_key(
        "documents_active_version_fkey",
        "documents",
        "document_versions",
        ["active_version"],
        ["id"],
    )
    op.create_table(
        "chunks",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("document_version_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("heading", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIMENSIONS), nullable=False),
        # `Computed(..., persisted=True)` vira `GENERATED ALWAYS AS (...) STORED`: o banco
        # calcula o `tsv` a cada escrita, e o código nunca o grava.
        sa.Column(
            "tsv",
            TSVECTOR(),
            sa.Computed(CHUNK_TSV_EXPRESSION, persisted=True),
            nullable=False,
        ),
        # `active` começa falso na ingestão e vira verdadeiro na publicação (seção 7.3).
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_version_id"],
            ["document_versions.id"],
            name="chunks_document_version_id_fkey",
        ),
        sa.PrimaryKeyConstraint("id", name="chunks_pkey"),
    )
    # HNSW com `vector_cosine_ops`, a classe do operador `<=>` da busca (seção 8.3), e GIN no
    # `tsv`. `postgresql_where` faz os dois índices parciais: só os chunks ativos (seção 8.2).
    op.create_index(
        "chunks_embedding_idx",
        "chunks",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_where=sa.text("active"),
    )
    op.create_index(
        "chunks_tsv_idx",
        "chunks",
        ["tsv"],
        unique=False,
        postgresql_using="gin",
        postgresql_where=sa.text("active"),
    )


def downgrade() -> None:
    """Apaga as três tabelas do corpus. Os documentos e os vetores se perdem."""
    op.drop_table("chunks")
    # A chave circular sai antes, senão `document_versions` não pode ser apagada.
    op.drop_constraint("documents_active_version_fkey", "documents", type_="foreignkey")
    op.drop_index("document_versions_document_id_idx", table_name="document_versions")
    op.drop_table("document_versions")
    op.drop_table("documents")
