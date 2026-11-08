"""Agregados e conversas para o admin. Seções 11.8, 12 e 18.3 do SDD.

A página de qualidade lê o banco, não o Prometheus, para funcionar sem o Grafana.

Camada de repositório (seção 6.2 do SDD). Só lê: `messages`, `feedback`, `conversations`,
`consent_records`, `registration_sessions`, `token_usage_days` e o nome e o e-mail de `users`.
Quem usa é o `InsightsService`, para a visão geral, a qualidade, o inspetor e a revelação de
identidade (FR-15). Os períodos chegam como `Window`, meio aberto: `start <= instante < end`.
As consultas por período filtram `messages.created_at`, que não tem índice, e percorrem a
tabela. Seção 15.5 do SDD.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.insights import CONVERSATION_PAGE, FeedbackFilter, FunnelStep, Window
from app.domain.registration import REGISTRATION_TTL

# Conversa que o inspetor pode abrir: de convidado ou de membro com melhoria vigente.
# Condição SQL reaproveitada na lista e na abertura de uma conversa (seção 11.8). Vale
# qualquer versão do consentimento `quality_improvement`, desde que não revogado. Uma conversa
# de convidado que virou de membro passa a depender do consentimento do membro.
_ELIGIBLE = (
    "(conversation.user_id IS NULL OR EXISTS ("
    "SELECT 1 FROM consent_records AS consent "
    "WHERE consent.user_id = conversation.user_id "
    "AND consent.purpose = 'quality_improvement' AND consent.revoked_at IS NULL))"
)


@dataclass(frozen=True, slots=True)
class ConversationRow:
    """Uma linha da tabela de conversas da página de qualidade, ainda sem pseudônimo."""

    id: UUID
    user_id: UUID | None
    guest_key_id: UUID | None
    created_at: datetime
    last_activity_at: datetime
    questions: int
    last_outcome: str | None
    helpful: int
    not_helpful: int


@dataclass(frozen=True, slots=True)
class InspectedMessage:
    """Uma mensagem no inspetor, com os dados de qualidade e a nota, se houver."""

    id: UUID
    role: str
    content: str
    created_at: datetime
    outcome: str | None
    prompt_version: str | None
    model: str | None
    request_id: str | None
    latency_ms: int | None
    langsmith_run_id: UUID | None
    citations: list[Any]
    rating: int | None


@dataclass(frozen=True, slots=True)
class ConversationOwner:
    """Os donos da conversa e se o inspetor pode abri-la."""

    id: UUID
    user_id: UUID | None
    guest_key_id: UUID | None
    created_at: datetime
    eligible: bool


class InsightsRepository:
    """Consultas de leitura do painel do admin."""

    def __init__(self, session: AsyncSession) -> None:
        """Usa a sessão aberta pelo serviço, sem abrir transação própria."""
        self._session = session

    async def question_count(self, window: Window) -> int:
        """Perguntas do período, de todas as conversas, elegíveis ou não (seção 12)."""
        value = await self._session.scalar(
            text(
                "SELECT count(*) FROM messages WHERE role = 'user' "
                "AND created_at >= :start AND created_at < :end"
            ),
            {"start": window.start, "end": window.end},
        )
        return int(value or 0)

    async def outcome_counts(self, window: Window) -> dict[str, int]:
        """Respostas do período por desfecho, como `{"answered": 12}`.

        Desfecho sem resposta no período fica fora do dicionário; o serviço completa com zero.
        """
        result = await self._session.execute(
            text(
                "SELECT outcome, count(*) FROM messages "
                "WHERE role = 'assistant' AND outcome IS NOT NULL "
                "AND created_at >= :start AND created_at < :end GROUP BY outcome"
            ),
            {"start": window.start, "end": window.end},
        )
        return {str(outcome): int(total) for outcome, total in result.all()}

    async def feedback_counts(self, window: Window) -> dict[int, int]:
        """Feedback das respostas do período, pela data da resposta.

        Devolve `{1: útil, -1: não útil}`. Uma nota dada hoje a uma resposta antiga conta no
        período da resposta, não no da nota.
        """
        result = await self._session.execute(
            text(
                "SELECT feedback.rating, count(*) FROM feedback "
                "JOIN messages ON messages.id = feedback.message_id "
                "WHERE messages.created_at >= :start AND messages.created_at < :end "
                "GROUP BY feedback.rating"
            ),
            {"start": window.start, "end": window.end},
        )
        return {int(rating): int(total) for rating, total in result.all()}

    async def daily(self, window: Window) -> dict[date, tuple[int, int]]:
        """Por dia UTC: (perguntas, respostas com desfecho answered).

        `created_at AT TIME ZONE 'UTC'` converte o `timestamptz` para o horário UTC antes de
        tirar a data, então o dia não depende do fuso da conexão. `count(*) FILTER (WHERE ...)`
        conta só as linhas que passam no filtro, e as duas contagens saem numa varredura só.
        Dia sem mensagem fica fora; o serviço completa com zeros.
        """
        result = await self._session.execute(
            text(
                "SELECT (created_at AT TIME ZONE 'UTC')::date AS day, "
                "count(*) FILTER (WHERE role = 'user'), "
                "count(*) FILTER (WHERE role = 'assistant' AND outcome = 'answered') "
                "FROM messages WHERE created_at >= :start AND created_at < :end "
                "GROUP BY day"
            ),
            {"start": window.start, "end": window.end},
        )
        return {row[0]: (int(row[1]), int(row[2])) for row in result.all()}

    async def funnel(self, window: Window) -> dict[str, dict[str, int]]:
        """Cadastros que começaram no período, por caminho e etapa alcançada.

        A sessão não guarda a criação; ela é `expires_at` menos a validade de 24 horas.

        Por isso a janela é deslocada em `REGISTRATION_TTL`: `expires_at` no período
        deslocado equivale a início no período pedido. As etapas: `started` conta todas;
        `password_set`, as que têm hash de senha ou foram concluídas, porque a conclusão
        apaga o hash; `completed`, as concluídas. O abandono também apaga o hash, então uma
        sessão abandonada depois da senha sai de `password_set`. A retenção apaga cada sessão
        na primeira execução do `retention-job` depois de `expires_at` (seção 11.6), então o
        funil só enxerga os cadastros que o job ainda não apagou. Devolve
        `{etapa: {"chat": n, "form": n}}`.
        """
        result = await self._session.execute(
            text(
                "SELECT path, count(*), "
                "count(*) FILTER (WHERE password_hash IS NOT NULL OR status = 'completed'), "
                "count(*) FILTER (WHERE status = 'completed') "
                "FROM registration_sessions "
                "WHERE expires_at >= :start AND expires_at < :end "
                "GROUP BY path"
            ),
            {"start": window.start + REGISTRATION_TTL, "end": window.end + REGISTRATION_TTL},
        )
        # Começa com zeros para as três etapas e os dois caminhos aparecerem sempre.
        steps: dict[str, dict[str, int]] = {
            step.value: {"chat": 0, "form": 0} for step in FunnelStep
        }
        for path, started, password, completed in result.all():
            key = str(path)
            steps[FunnelStep.STARTED.value][key] = int(started)
            steps[FunnelStep.PASSWORD_SET.value][key] = int(password)
            steps[FunnelStep.COMPLETED.value][key] = int(completed)
        return steps

    async def tokens_on(self, day: date) -> int:
        """Tokens de entrada mais saída gastos no dia, ou 0 sem linha no contador."""
        value = await self._session.scalar(
            text(
                "SELECT coalesce(input_tokens + output_tokens, 0) "
                "FROM token_usage_days WHERE day = :day"
            ),
            {"day": day},
        )
        return int(value or 0)

    async def conversations(
        self,
        window: Window,
        *,
        outcome: str | None,
        feedback: FeedbackFilter | None,
    ) -> list[ConversationRow]:
        """Conversas com atividade no período que o inspetor pode abrir.

        Até `CONVERSATION_PAGE` (50) conversas, da última atividade mais recente para a mais
        antiga (seção 12). Os filtros são texto fixo deste arquivo; os valores do admin vão
        em parâmetros.

        1. Monta os filtros: elegibilidade, última atividade no período e, quando pedidos,
           desfecho e feedback.
        2. Calcula as estatísticas de cada conversa num `JOIN LATERAL` sobre as mensagens.
        3. Aplica os filtros, ordena pela última atividade e corta na página.
        """
        # 1. O filtro de desfecho olha a conversa inteira, não só o período: basta uma
        # resposta da conversa com aquele desfecho.
        filters = [_ELIGIBLE, "stats.last_activity_at >= :start", "stats.last_activity_at < :end"]
        params: dict[str, Any] = {
            "start": window.start,
            "end": window.end,
            "limit": CONVERSATION_PAGE,
        }
        if outcome is not None:
            filters.append(
                "EXISTS (SELECT 1 FROM messages AS hit WHERE hit.conversation_id = "
                "conversation.id AND hit.role = 'assistant' AND hit.outcome = :outcome)"
            )
            params["outcome"] = outcome
        if feedback is FeedbackFilter.HELPFUL:
            filters.append("stats.helpful > 0")
        elif feedback is FeedbackFilter.NOT_HELPFUL:
            filters.append("stats.not_helpful > 0")
        elif feedback is FeedbackFilter.NONE:
            filters.append("stats.helpful = 0 AND stats.not_helpful = 0")
        # 2. e 3.
        result = await self._session.execute(
            text(
                "SELECT conversation.id, conversation.user_id, conversation.guest_key_id, "
                "conversation.created_at, stats.last_activity_at, stats.questions, "
                "stats.last_outcome, stats.helpful, stats.not_helpful "
                "FROM conversations AS conversation "
                # `JOIN LATERAL` roda a subconsulta uma vez por conversa, citando
                # `conversation.id`. Última atividade é a mensagem mais nova. `array_agg` com
                # `ORDER BY ... DESC` junta os desfechos das respostas, do mais novo ao mais
                # antigo, e `[1]` pega o primeiro, porque o array do PostgreSQL começa em 1. O
                # `LEFT JOIN feedback` não duplica linhas: cada mensagem tem no máximo uma nota.
                "JOIN LATERAL ("
                "SELECT max(message.created_at) AS last_activity_at, "
                "count(*) FILTER (WHERE message.role = 'user') AS questions, "
                "(array_agg(message.outcome ORDER BY message.created_at DESC) "
                "FILTER (WHERE message.role = 'assistant'))[1] AS last_outcome, "
                "count(feedback.message_id) FILTER (WHERE feedback.rating = 1) AS helpful, "
                "count(feedback.message_id) FILTER (WHERE feedback.rating = -1) AS not_helpful "
                "FROM messages AS message "
                "LEFT JOIN feedback ON feedback.message_id = message.id "
                "WHERE message.conversation_id = conversation.id"
                # Uma agregação sem `GROUP BY` sempre devolve uma linha, mesmo sem mensagens.
                # O `max` nulo marca a conversa vazia, que fica de fora.
                ") AS stats ON stats.last_activity_at IS NOT NULL "
                "WHERE " + " AND ".join(filters) + " "
                "ORDER BY stats.last_activity_at DESC LIMIT :limit"
            ),
            params,
        )
        return [
            ConversationRow(
                id=row[0],
                user_id=row[1],
                guest_key_id=row[2],
                created_at=row[3],
                last_activity_at=row[4],
                questions=int(row[5]),
                last_outcome=None if row[6] is None else str(row[6]),
                helpful=int(row[7]),
                not_helpful=int(row[8]),
            )
            for row in result.all()
        ]

    async def owner(self, conversation_id: UUID) -> ConversationOwner | None:
        """Donos da conversa e se ela é elegível ao inspetor, ou `None` se não existe.

        O serviço responde 404 também para a conversa que existe mas não é elegível, sem
        gravar auditoria (seção 12).
        """
        result = await self._session.execute(
            text(
                "SELECT conversation.id, conversation.user_id, conversation.guest_key_id, "
                "conversation.created_at, " + _ELIGIBLE + " AS eligible "
                "FROM conversations AS conversation WHERE conversation.id = :id"
            ),
            {"id": conversation_id},
        )
        row = result.first()
        if row is None:
            return None
        return ConversationOwner(
            id=row[0],
            user_id=row[1],
            guest_key_id=row[2],
            created_at=row[3],
            eligible=bool(row[4]),
        )

    async def messages(self, conversation_id: UUID) -> list[InspectedMessage]:
        """Mensagens da conversa para o inspetor, com a nota de cada resposta.

        O `LEFT JOIN feedback` mantém as mensagens sem nota, com `rating` nulo. A ordem é por
        data; `role` desempata, e `assistant` vem antes de `user` na ordem alfabética.
        """
        result = await self._session.execute(
            text(
                "SELECT message.id, message.role, message.content, message.created_at, "
                "message.outcome, message.prompt_version, message.model, message.request_id, "
                "message.latency_ms, message.langsmith_run_id, message.citations, "
                "feedback.rating "
                "FROM messages AS message "
                "LEFT JOIN feedback ON feedback.message_id = message.id "
                "WHERE message.conversation_id = :id ORDER BY message.created_at, message.role"
            ),
            {"id": conversation_id},
        )
        return [
            InspectedMessage(
                id=row[0],
                role=str(row[1]),
                content=str(row[2]),
                created_at=row[3],
                outcome=row[4],
                prompt_version=row[5],
                model=row[6],
                request_id=row[7],
                latency_ms=row[8],
                langsmith_run_id=row[9],
                citations=list(row[10] or []),
                rating=None if row[11] is None else int(row[11]),
            )
            for row in result.all()
        ]

    async def identity(self, user_id: UUID) -> tuple[str, str] | None:
        """Nome e e-mail do membro, só para a revelação de identidade com motivo (seção 11.8)."""
        result = await self._session.execute(
            text("SELECT full_name, email FROM users WHERE id = :id"), {"id": user_id}
        )
        row = result.first()
        if row is None:
            return None
        return str(row[0]), str(row[1])
