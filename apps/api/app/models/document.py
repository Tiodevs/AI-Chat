"""Tabela `documents`: os documentos do corpus. Seções 7.3 e 8.1 do SDD.

Camada de entidade de persistência (seção 6.2 do SDD). `DocumentRepository` cria, trava,
publica e arquiva documentos, e `RetrievalRepository` filtra a busca por eles. Criada na
migração `0002_corpus`.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Document(Base):
    """Um documento do corpus, com várias versões em `document_versions`.

    A busca só usa a versão apontada por `active_version` (seção 8.2). Uma versão nova só
    toma o lugar da ativa quando chega a `ready` (FR-11). A API não apaga documentos: arquivar
    tira o documento da busca (FR-12). A tabela não tem dado pessoal, e por isso não tem regra
    de retenção.
    """

    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'archived')", name="documents_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    # Título mostrado nas citações. Publicar uma versão grava o título dela.
    title: Mapped[str] = mapped_column(Text, nullable=False)
    # Único. Na semente, é o nome do arquivo sem extensão. No upload do admin, vem de
    # `slugify` e ganha `-2`, `-3` quando já existe (seção 12).
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    # Nulo até a primeira versão chegar a `ready`. `documents` e `document_versions` apontam
    # uma para a outra, e `use_alter=True` faz essa chave estrangeira nascer num `ALTER TABLE`
    # depois das duas tabelas. A migração `0002_corpus` faz o mesmo.
    active_version: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "document_versions.id",
            use_alter=True,
            name="documents_active_version_fkey",
        ),
        nullable=True,
    )
    # O admin que enviou, ou o admin mais antigo, na semente. Sem `ondelete`: um admin com
    # documentos não pode ser apagado enquanto eles apontarem para ele.
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    # O repositório grava `now()` a cada versão nova, publicação e arquivamento. A lista do
    # admin ordena por esta coluna.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
