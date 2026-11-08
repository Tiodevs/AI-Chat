"""Tabela `document_versions`: cada arquivo enviado de um documento. Seções 7.3 e 8.1 do SDD.

Camada de entidade de persistência (seção 6.2 do SDD). `DocumentRepository` grava a versão em
`processing`, publica ou marca a falha, e lê os bytes para tentar de novo. Criada na migração
`0002_corpus`.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DocumentVersion(Base):
    """Uma versão de um documento e o estado da ingestão dela.

    A versão nasce em `processing`, com o texto vazio, e termina em `ready` ou `failed`
    (seção 7.3). A API não apaga versões: as antigas ficam, com os chunks desativados.
    """

    __tablename__ = "document_versions"
    __table_args__ = (
        # Numeração 1, 2, 3 por documento. O repositório calcula a próxima com o documento
        # travado, e a restrição barra um número repetido mesmo assim.
        UniqueConstraint(
            "document_id",
            "version",
            name="document_versions_document_id_version_key",
        ),
        CheckConstraint(
            "ingestion_status IN ('processing', 'ready', 'failed')",
            name="document_versions_ingestion_status",
        ),
        # B-tree da seção 8.2. O índice da restrição única também começa por `document_id`.
        Index("document_versions_document_id_idx", "document_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    # Sem `ondelete`: versões não são apagadas.
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    # Vem da extensão do arquivo, nunca do navegador: `text/markdown`, `text/plain` ou
    # `application/pdf` (seção 12).
    media_type: Mapped[str] = mapped_column(Text, nullable=False)
    # SHA-256 em hexadecimal dos bytes. A semente compara com ele para pular arquivo que não
    # mudou.
    sha256: Mapped[str] = mapped_column(Text, nullable=False)
    # Texto extraído. Vazio enquanto a versão está em `processing`.
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    # `LargeBinary` vira `bytea` no PostgreSQL. Os bytes originais ficam guardados para
    # "Tentar de novo" criar uma versão nova sem outro upload.
    original_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    ingestion_status: Mapped[str] = mapped_column(Text, nullable=False)
    # Mensagem de leitura da falha, de `app.prompts.corpus`. Nula fora de `failed`.
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Horário do banco no INSERT. Uma versão em `processing` há mais de 15 minutos, contados
    # daqui, passa a `failed` na subida da API (seção 7.3).
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
