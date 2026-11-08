"""Visão geral, qualidade, inspetor e revelação de identidade do admin.

Seções 11.8, 12, 15.5 e 18.3 do SDD. Abrir uma conversa grava `conversation.view`.
Revelar exige motivo e grava `identity.reveal` (FR-15).

Camada de serviço. `controllers/admin_insights.py` confere o admin com `require_admin` e
chama `InsightsService`, montado por pedido em `core/container.py:get_insights_service`
com `PSEUDONYM_KEY`, `LLM_DAILY_TOKEN_BUDGET` e `LANGSMITH_RUN_URL_TEMPLATE`. Os números vêm
de agregados do banco (`InsightsRepository`), não do Prometheus, para a página funcionar
sem o Grafana (seção 18.3). As contas e as janelas ficam em `domain/insights.py`.

Privacidade (seção 11.8): o inspetor só abre conversas de convidado e de membro com
`quality_improvement` vigente; as demais entram só nos agregados. O admin vê um pseudônimo
de 8 caracteres, nunca nome nem e-mail, até revelar a identidade com um motivo auditado.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from uuid import UUID

from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.errors import Conflict, NotFound, ValidationFailed
from app.domain.insights import (
    FeedbackFilter,
    InsightAction,
    abstentions,
    budget_ratio,
    clean_reason,
    days_of,
    intent_counts,
    rate,
    short_pseudonym,
    trace_url,
    valid_period,
    windows_for,
)
from app.domain.outcomes import Outcome
from app.domain.pseudonym import subject_pseudonym
from app.ports.clock import Clock
from app.prompts.conversations import CONVERSATION_NOT_FOUND
from app.prompts.insights import (
    CONVERSATION_HIDDEN,
    FILTER_INVALID,
    GUEST_HAS_NO_IDENTITY,
    PERIOD_INVALID,
    REASON_INVALID,
)
from app.repositories.audit import AuditRepository
from app.repositories.insights import ConversationOwner, InsightsRepository

# `target_type` dos eventos `conversation.view` e `identity.reveal` (seção 8.1).
TARGET_TYPE = "conversation"


@dataclass(frozen=True, slots=True)
class Metric:
    """Um indicador no período atual e no anterior. `None` quando falta denominador."""

    current: float | None
    previous: float | None


@dataclass(frozen=True, slots=True)
class TrendPoint:
    """Perguntas e respostas `answered` de um dia UTC."""

    day: date
    questions: int
    answered: int


@dataclass(frozen=True, slots=True)
class FunnelRow:
    """Uma etapa do funil de cadastro (`started`, `password_set`, `completed`) por caminho."""

    step: str
    chat: int
    form: int


@dataclass(frozen=True, slots=True)
class Budget:
    """Tokens usados hoje, o teto diário e a razão entre os dois (0 com o teto desligado)."""

    used_tokens: int
    daily_budget: int
    ratio: float


@dataclass(frozen=True, slots=True)
class Overview:
    """Tudo o que `GET /v1/admin/overview` devolve (seção 12)."""

    period_days: int
    generated_at: datetime
    questions: Metric
    answer_rate: Metric
    abstention_rate: Metric
    helpful_rate: Metric
    trend: list[TrendPoint]
    outcomes: dict[str, int]
    intents: dict[str, int]
    feedback: dict[str, int]
    funnel: list[FunnelRow]
    budget: Budget


@dataclass(frozen=True, slots=True)
class ConversationSummary:
    """Uma linha da lista de qualidade. Só pseudônimo, contagens e desfechos."""

    id: UUID
    subject_kind: str
    pseudonym: str
    started_at: datetime
    last_activity_at: datetime
    questions: int
    last_outcome: str | None
    helpful: int
    not_helpful: int


@dataclass(frozen=True, slots=True)
class Quality:
    """`GET /v1/admin/quality`: agregados de todas as conversas e a lista das elegíveis."""

    period_days: int
    outcomes: dict[str, int]
    feedback: dict[str, int]
    conversations: list[ConversationSummary]


@dataclass(frozen=True, slots=True)
class InspectorMessage:
    """Mensagem no inspetor, com os dados de diagnóstico da seção 18.5.

    `trace_url` é o link do run no LangSmith, ou `None` sem `LANGSMITH_RUN_URL_TEMPLATE`.
    As citações levam índice, título e seção, sem id de chunk.
    """

    id: UUID
    role: str
    content: str
    created_at: datetime
    outcome: str | None
    prompt_version: str | None
    model: str | None
    request_id: str | None
    latency_ms: int | None
    run_id: UUID | None
    trace_url: str | None
    citations: list[dict[str, Any]]
    rating: int | None


@dataclass(frozen=True, slots=True)
class Inspection:
    """A conversa pseudonimizada que o inspetor mostra."""

    id: UUID
    subject_kind: str
    pseudonym: str
    created_at: datetime
    messages: list[InspectorMessage]


@dataclass(frozen=True, slots=True)
class Identity:
    """Nome e e-mail do membro dono da conversa, revelados com motivo."""

    conversation_id: UUID
    full_name: str
    email: str


class InsightsService:
    """Painéis e inspetor do admin. `admin_id` já vem conferido pelo controlador.

    `pseudonym_key` é a `PSEUDONYM_KEY` do HMAC, `daily_budget` o teto de tokens e
    `run_url_template` o modelo de link de run do LangSmith, com `{run_id}`.
    """

    def __init__(
        self,
        *,
        database_url: str,
        clock: Clock,
        pseudonym_key: str,
        daily_budget: int,
        run_url_template: str,
    ) -> None:
        self._database_url = database_url
        self._clock = clock
        self._pseudonym_key = pseudonym_key
        self._daily_budget = daily_budget
        self._run_url_template = run_url_template

    async def overview(self, period_days: int) -> Overview:
        """Indicadores do período contra o período anterior de mesmo tamanho.

        1. Aceita só 7 ou 30 dias (422).
        2. O período atual termina agora; o anterior termina onde o atual começa.
        3. Lê todos os agregados numa transação curta de leitura.
        4. Calcula as taxas no domínio. Sem denominador, a taxa é `None`.

        A intenção vem do desfecho gravado, porque a mensagem não guarda a intenção:
        `refused` conta como `medical_advice`, `off_topic` como `off_topic`, e todo o resto,
        inclusive `degraded`, `error` e `cancelled`, como `public_info`. O orçamento é o do
        dia UTC de agora.
        """
        # 1.
        _check_period(period_days)
        now = self._clock.now()
        # 2.
        windows = windows_for(now, period_days)
        # 3.
        async with open_session(self._database_url) as session, UnitOfWork(session):
            repository = InsightsRepository(session)
            questions = await repository.question_count(windows.current)
            previous_questions = await repository.question_count(windows.previous)
            outcomes = await repository.outcome_counts(windows.current)
            previous_outcomes = await repository.outcome_counts(windows.previous)
            ratings = await repository.feedback_counts(windows.current)
            previous_ratings = await repository.feedback_counts(windows.previous)
            daily = await repository.daily(windows.current)
            # O funil lê `registration_sessions`, que o `retention-job` apaga depois do
            # `expires_at`. Com o job rodando, ele só vê os cadastros das últimas 24 a 48 h.
            funnel = await repository.funnel(windows.current)
            used = await repository.tokens_on(now.date())
        # 4.
        return Overview(
            period_days=period_days,
            generated_at=now,
            questions=Metric(float(questions), float(previous_questions)),
            answer_rate=Metric(_answer_rate(outcomes), _answer_rate(previous_outcomes)),
            abstention_rate=Metric(
                _abstention_rate(outcomes), _abstention_rate(previous_outcomes)
            ),
            helpful_rate=Metric(_helpful_rate(ratings), _helpful_rate(previous_ratings)),
            # Um ponto por dia UTC que o período toca, com zero nos dias sem mensagem.
            trend=[
                TrendPoint(day, *daily.get(day, (0, 0))) for day in days_of(windows.current)
            ],
            outcomes={item.value: outcomes.get(item.value, 0) for item in Outcome},
            intents=intent_counts(outcomes),
            feedback=_feedback(ratings, sum(outcomes.values())),
            funnel=[FunnelRow(step, row["chat"], row["form"]) for step, row in funnel.items()],
            budget=Budget(used, self._daily_budget, budget_ratio(used, self._daily_budget)),
        )

    async def quality(
        self, *, period_days: int, outcome: str | None, feedback: str | None
    ) -> Quality:
        """Desfechos e feedback do período e até 50 conversas que o inspetor pode abrir.

        Valida o período e os filtros (`outcome` um desfecho conhecido, `feedback` em
        `helpful`, `not_helpful` ou `none`); um valor fora disso responde 422 em
        `field_errors`. Os agregados contam todas as conversas. A lista só traz as elegíveis
        da seção 11.8, da atividade mais recente para a mais antiga, com pseudônimo. Uma
        transação curta de leitura.
        """
        _check_period(period_days)
        if outcome is not None and outcome not in {item.value for item in Outcome}:
            raise ValidationFailed(FILTER_INVALID, field_errors={"outcome": FILTER_INVALID})
        if feedback is not None and feedback not in {item.value for item in FeedbackFilter}:
            raise ValidationFailed(FILTER_INVALID, field_errors={"feedback": FILTER_INVALID})
        window = windows_for(self._clock.now(), period_days).current
        async with open_session(self._database_url) as session, UnitOfWork(session):
            repository = InsightsRepository(session)
            outcomes = await repository.outcome_counts(window)
            ratings = await repository.feedback_counts(window)
            rows = await repository.conversations(
                window,
                outcome=outcome,
                feedback=None if feedback is None else FeedbackFilter(feedback),
            )
        return Quality(
            period_days=period_days,
            outcomes={item.value: outcomes.get(item.value, 0) for item in Outcome},
            feedback=_feedback(ratings, sum(outcomes.values())),
            conversations=[
                ConversationSummary(
                    id=row.id,
                    subject_kind=_kind(row.user_id),
                    pseudonym=self._pseudonym(row.user_id, row.guest_key_id),
                    started_at=row.created_at,
                    last_activity_at=row.last_activity_at,
                    questions=row.questions,
                    last_outcome=row.last_outcome,
                    helpful=row.helpful,
                    not_helpful=row.not_helpful,
                )
                for row in rows
            ],
        )

    async def inspect(self, *, admin_id: UUID, conversation_id: UUID) -> Inspection:
        """Abre a conversa no inspetor e grava `conversation.view` na mesma transação.

        Conversa inexistente, ou de membro sem `quality_improvement` vigente, responde 404.
        Como o erro sobe de dentro da transação, ela é desfeita e nada fica gravado. A
        leitura das mensagens e a auditoria confirmam juntas.
        """
        async with open_session(self._database_url) as session, UnitOfWork(session):
            repository = InsightsRepository(session)
            owner = await _eligible_owner(repository, conversation_id)
            messages = await repository.messages(conversation_id)
            await AuditRepository(session).record(
                actor_user_id=admin_id,
                action=InsightAction.CONVERSATION_VIEW.value,
                target_type=TARGET_TYPE,
                target_id=conversation_id,
                created_at=self._clock.now(),
            )
        return Inspection(
            id=owner.id,
            subject_kind=_kind(owner.user_id),
            pseudonym=self._pseudonym(owner.user_id, owner.guest_key_id),
            created_at=owner.created_at,
            messages=[
                InspectorMessage(
                    id=message.id,
                    role=message.role,
                    content=message.content,
                    created_at=message.created_at,
                    outcome=message.outcome,
                    prompt_version=message.prompt_version,
                    model=message.model,
                    request_id=message.request_id,
                    latency_ms=message.latency_ms,
                    run_id=message.langsmith_run_id,
                    trace_url=trace_url(self._run_url_template, message.langsmith_run_id),
                    citations=[_citation(item) for item in message.citations],
                    rating=message.rating,
                )
                for message in messages
            ],
        )

    async def reveal(self, *, admin_id: UUID, conversation_id: UUID, reason: str) -> Identity:
        """Devolve nome e e-mail do membro e grava `identity.reveal` com o motivo (FR-15).

        1. O motivo precisa ter de 10 a 500 caracteres depois de juntar os espaços (422 em
           `field_errors.reason`).
        2. Numa transação: a conversa precisa estar no inspetor (404), ser de membro (409
           para convidado, que não tem identidade) e o usuário precisa existir (404).
        3. Grava a auditoria com o motivo limpo na mesma transação da leitura.
        """
        # 1.
        clean = clean_reason(reason)
        if clean is None:
            raise ValidationFailed(REASON_INVALID, field_errors={"reason": REASON_INVALID})
        # 2.
        async with open_session(self._database_url) as session, UnitOfWork(session):
            repository = InsightsRepository(session)
            owner = await _eligible_owner(repository, conversation_id)
            if owner.user_id is None:
                raise Conflict(GUEST_HAS_NO_IDENTITY)
            identity = await repository.identity(owner.user_id)
            if identity is None:
                raise NotFound(CONVERSATION_NOT_FOUND)
            revealed = Identity(
                conversation_id=conversation_id, full_name=identity[0], email=identity[1]
            )
            # 3. O motivo fica; o nome e o e-mail não entram na auditoria.
            await AuditRepository(session).record(
                actor_user_id=admin_id,
                action=InsightAction.IDENTITY_REVEAL.value,
                target_type=TARGET_TYPE,
                target_id=conversation_id,
                reason=clean,
                created_at=self._clock.now(),
            )
        return revealed

    def _pseudonym(self, user_id: UUID | None, guest_key_id: UUID | None) -> str:
        """Os 8 primeiros caracteres do HMAC do id do membro ou da chave de convidado.

        Sem `PSEUDONYM_KEY`, `subject_pseudonym` levanta `ValueError`. A conferência de
        subida exige a chave em `development` e `production`.
        """
        subject = user_id or guest_key_id
        if subject is None:
            return ""
        return short_pseudonym(subject_pseudonym(subject, self._pseudonym_key))


async def _eligible_owner(
    repository: InsightsRepository, conversation_id: UUID
) -> ConversationOwner:
    """Dono da conversa, se o inspetor pode abri-la. Senão, `NotFound` (404)."""
    owner = await repository.owner(conversation_id)
    if owner is None:
        raise NotFound(CONVERSATION_NOT_FOUND)
    if not owner.eligible:
        # Sem o consentimento de melhoria, a conversa fica só nos agregados (11.8).
        raise NotFound(CONVERSATION_HIDDEN)
    return owner


def _check_period(period_days: int) -> None:
    """Só 7 ou 30 dias. Outro valor responde 422 em `field_errors.period_days`."""
    if not valid_period(period_days):
        raise ValidationFailed(PERIOD_INVALID, field_errors={"period_days": PERIOD_INVALID})


def _kind(user_id: UUID | None) -> str:
    """`guest` sem `user_id`, `member` com ele."""
    return "guest" if user_id is None else "member"


def _answer_rate(outcomes: dict[str, int]) -> float | None:
    """Respostas `answered` sobre todos os desfechos do período."""
    return rate(outcomes.get(Outcome.ANSWERED.value, 0), sum(outcomes.values()))


def _abstention_rate(outcomes: dict[str, int]) -> float | None:
    """`abstained` mais `grounding_failed` sobre todos os desfechos do período."""
    return rate(abstentions(outcomes), sum(outcomes.values()))


def _helpful_rate(ratings: dict[int, int]) -> float | None:
    """Notas úteis sobre todas as notas dadas. Respostas sem nota ficam de fora."""
    return rate(ratings.get(1, 0), ratings.get(1, 0) + ratings.get(-1, 0))


def _feedback(ratings: dict[int, int], answers: int) -> dict[str, int]:
    """Contagem por nota. `none` são as respostas do período que ninguém avaliou."""
    helpful = ratings.get(1, 0)
    not_helpful = ratings.get(-1, 0)
    return {
        FeedbackFilter.HELPFUL.value: helpful,
        FeedbackFilter.NOT_HELPFUL.value: not_helpful,
        FeedbackFilter.NONE.value: max(0, answers - helpful - not_helpful),
    }


def _citation(item: object) -> dict[str, Any]:
    """Só índice, título e seção. O id do chunk não sai para a tela."""
    if not isinstance(item, dict):
        return {"index": 0, "document_title": "", "heading": None}
    heading = item.get("heading")
    return {
        "index": int(item.get("index", 0)),
        "document_title": str(item.get("document_title", "")),
        "heading": None if heading is None else str(heading),
    }
