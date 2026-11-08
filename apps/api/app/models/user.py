"""Tabela `users`: membros e admins. Seção 8.1 do SDD.

Camada de entidade de persistência (seção 6.2 do SDD). `UserRepository` lê e grava a tabela, e
`RetentionRepository` apaga membros inativos. Os serviços de autenticação, conta e cadastro
recebem a entidade `User` dos repositórios. Criada na migração `0001_initial`; a restrição de
`visit_reason` entrou na `0005_registration`.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.fields import VISIT_REASON_CHECK_SQL
from app.models.base import Base


class User(Base):
    """Uma conta. Os dados pessoais seguem as regras de campo da seção 8.5.

    Tabelas que apontam para `users`, e o que acontece com elas quando a conta é apagada:
    `consent_records`, `registration_sessions` e `conversations` somem em cascata, e as
    mensagens e o feedback vão junto com as conversas. `data_subject_requests.user_id` vira
    nulo. `auth_sessions` e `documents.created_by` não têm cascata: as sessões precisam ser
    apagadas antes. `audit_events` não tem chave estrangeira, para sobreviver à exclusão.

    Retenção (seção 11.6): a conta fica até ser excluída. Um membro que passa 24 meses sem
    entrar é eliminado pelo `retention-job`. Contas de admin seguem a seção 10.5.
    """

    __tablename__ = "users"
    __table_args__ = (
        # O banco garante o e-mail em minúsculas (seção 8). Quem grava normaliza antes.
        CheckConstraint("email = lower(email)", name="users_email_lowercase"),
        # Só dois papéis. O cadastro público fixa `member` no código (seção 10.5).
        CheckConstraint("role IN ('member', 'admin')", name="users_role"),
        CheckConstraint(
            "visitor_type IS NULL OR visitor_type IN ('patient', 'visitor', 'caregiver')",
            name="users_visitor_type",
        ),
        # A lista fechada de motivos vem de `app.domain.fields`, a mesma do formulário.
        CheckConstraint(VISIT_REASON_CHECK_SQL, name="users_visit_reason"),
    )

    # `gen_random_uuid()` só vale quando o INSERT não traz o id. O `UserRepository.insert`
    # gera o id com `uuid4()` no Python e devolve esse valor.
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    # `unique=True` cria a restrição `users_email_key`. O índice dela serve o login.
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    # Hash argon2id da senha. A senha nunca é gravada nem devolvida (seção 8.5).
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    # `visitor_type` e `visit_reason` só ficam preenchidos com o consentimento de
    # personalização, porque podem indicar que a pessoa é paciente (seção 7.2). Revogar o
    # consentimento limpa os dois.
    visitor_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    visit_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    # Última entrada. O login atualiza (`UserRepository.touch`), e a regra de contas
    # inativas da retenção compara com ela.
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    # `timestamptz` com padrão `now()` no banco. Os repositórios gravam o horário do `Clock`
    # do serviço, para os testes controlarem o tempo.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
