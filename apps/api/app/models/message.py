"""Tabela `messages`: perguntas do visitante e respostas do assistente. Seções 7.1 e 8.1.

Camada de entidade de persistência (seção 6.2 do SDD). `ConversationRepository` grava e lê as
mensagens de uma conversa, `InsightsRepository` as agrega para o admin, e `RetentionRepository`
usa a mais nova para saber a última atividade. Criada na migração `0004_conversations`; a
`0009_message_request_id` acrescentou `request_id`, e a `0010_handoffs`, as colunas do
atendimento humano (seção 29.7).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.handoff import RedactionCategory, check_sql
from app.domain.outcomes import OUTCOME_CHECK_SQL
from app.models.base import Base


class Message(Base):
    """Uma mensagem. A pergunta tem `role = user`, e a resposta, `role = assistant`.

    No atendimento humano, o visitante escreve com `role = user` e a equipe com
    `role = attendant`, as duas com `handoff_id` e `seq` (seção 29.7).

    Uma pergunta gera duas linhas, em duas transações curtas (seção 6.4). A pergunta não tem
    desfecho, citação, modelo nem tokens. A resposta traz tudo isso. Retenção: a mensagem some
    com a conversa (seção 11.6).
    """

    __tablename__ = "messages"
    __table_args__ = (
        # Chave de idempotência do envio (seção 7.1): um reenvio do mesmo `client_message_id`
        # bate aqui, e o serviço responde 409 com o id já gravado. O PostgreSQL trata nulos
        # como diferentes numa restrição única, então as respostas, sem `client_message_id`,
        # nunca colidem entre si.
        UniqueConstraint(
            "conversation_id",
            "client_message_id",
            name="messages_conversation_id_client_message_id_key",
        ),
        # `attendant` é a pessoa da equipe no atendimento humano (seção 29.7).
        CheckConstraint("role IN ('user', 'assistant', 'attendant')", name="messages_role"),
        # A mensagem da equipe é sempre do atendimento, e a do atendimento sempre tem `seq`.
        CheckConstraint(
            "role <> 'attendant' OR handoff_id IS NOT NULL",
            name="messages_attendant_handoff",
        ),
        CheckConstraint("handoff_id IS NULL OR seq IS NOT NULL", name="messages_handoff_seq"),
        CheckConstraint(
            f"redaction IS NULL OR {check_sql('redaction', RedactionCategory)}",
            name="messages_redaction",
        ),
        # O cursor da retomada do fluxo: um `seq` por mensagem do atendimento (seção 29.6).
        UniqueConstraint("handoff_id", "seq", name="messages_handoff_id_seq_key"),
        # Nulo ou um dos desfechos de `Outcome` (seção 7.1).
        CheckConstraint(OUTCOME_CHECK_SQL, name="messages_outcome"),
        CheckConstraint("input_tokens >= 0 AND output_tokens >= 0", name="messages_tokens"),
        # B-tree da seção 8.2. O índice da restrição única já começa por `conversation_id`,
        # então este repete o trabalho dele; a Etapa 13.5 o remove.
        Index("messages_conversation_id_idx", "conversation_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    # UUID que o navegador gera para cada pergunta. Nulo nas respostas.
    client_message_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    # Numa pergunta de orientação médica, o texto vira o marcador
    # `[health-related message not stored]` antes de chegar aqui (seção 11.4).
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Lista de `{index, document_title, heading, chunk_id}`, uma por citação mantida. `[]` na
    # pergunta. O `chunk_id` fica dentro do JSON, então não há chave estrangeira para `chunks`.
    citations: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    # Modelo e versão do prompt que geraram a resposta. Nulos na pergunta.
    model: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Tokens que o adaptador contou, mesmo de uma resposta cancelada (seção 6.4). Zero na
    # pergunta.
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Desfecho da resposta: `answered`, `abstained`, `refused` e os outros da seção 7.1.
    # Nulo na pergunta.
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Id do rastro no LangSmith. O serviço usa o próprio id da resposta como id do rastro.
    langsmith_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    # Id do pedido HTTP que gravou a mensagem, para o inspetor de qualidade cruzar com os logs.
    request_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Sem padrão no banco. O serviço grava `allocate_created_at`: o horário atual ou, se ele
    # não passa da mensagem mais nova da conversa, um microssegundo depois dela.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # As cinco colunas abaixo são do atendimento humano (seção 29.7, migração `0010`). Uma
    # mensagem com `handoff_id` é do atendimento e nunca vai ao modelo (FR-21).
    handoff_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("handoffs.id", ondelete="CASCADE"),
        nullable=True,
    )
    # O cursor da retomada do fluxo. Uma remoção dá à mensagem um `seq` novo (seção 29.6).
    seq: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Quem da equipe escreveu. Sem chave estrangeira, como em `audit_events`: a autoria
    # sobrevive à revogação do papel e à exclusão da conta.
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    # A categoria da remoção do conteúdo, ou `retention` quando a regra de 90 dias apagou.
    redaction: Mapped[str | None] = mapped_column(Text, nullable=True)
    redacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
