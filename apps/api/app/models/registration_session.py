"""Tabela `registration_sessions`: o estado de um cadastro em andamento. Seções 7.2 e 8.1.

Camada de entidade de persistência (seção 6.2 do SDD). `RegistrationRepository` grava e trava
as linhas para o `RegistrationService`, `InsightsRepository.funnel` conta o funil do admin, e
`RetentionRepository` apaga as vencidas. Criada na migração `0005_registration`.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.registration import PATH_CHECK_SQL, STATUS_CHECK_SQL
from app.models.base import Base


class RegistrationSession(Base):
    """Uma sessão de cadastro, pelo chat ou pelo formulário.

    O LangGraph não guarda estado: o serviço carrega esta linha, roda o grafo e grava o
    resultado (seção 7.2). A transcrição não tem campo de senha. Na conclusão e no abandono, o
    serviço apaga a transcrição e o hash da senha, e os campos ficam até a linha sair.
    Retenção: a linha some quando `expires_at` passa, 24 horas depois do início (seção 11.6).
    A Etapa 13.3 acrescenta uma coluna `version`, para duas gravações na mesma sessão não
    apagarem uma à outra.
    """

    __tablename__ = "registration_sessions"
    __table_args__ = (
        # Os estados da máquina da seção 7.2, tirados do enum `Status` do domínio.
        CheckConstraint(STATUS_CHECK_SQL, name="registration_sessions_status"),
        # `chat` ou `form`.
        CheckConstraint(PATH_CHECK_SQL, name="registration_sessions_path"),
        Index("registration_sessions_user_id_idx", "user_id"),
    )

    # Sem padrão no banco: o serviço gera o id antes do INSERT. O id é a chave de idempotência
    # do aceite, então repetir o aceite devolve o mesmo usuário (seção 7.2).
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    # JSONB é JSON em formato binário do PostgreSQL. O SQLAlchemy converte de e para `dict`.
    # O documento vem de `fields_document`: os cinco campos, as marcas de campo pulado,
    # `correcting`, `next_step` e os erros de campo.
    fields: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # Hash argon2id gravado no passo da senha. A senha em si nunca chega ao banco.
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Lista de `{role, text, created_at}` (`TranscriptItem`). O repositório grava a lista
    # inteira a cada turno, nunca um item dentro dela.
    transcript: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    # Preenchido na conclusão. `ondelete="CASCADE"`: a sessão some com a conta.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    # Início mais 24 horas (`REGISTRATION_TTL`). A tabela não tem `created_at`, então o funil
    # do admin calcula o início como `expires_at` menos 24 horas.
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
