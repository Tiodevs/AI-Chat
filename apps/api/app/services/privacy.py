"""Canal do titular e fila do admin. Seções 10.4, 11.5, 12 e 15.5 do SDD.

Mudar o status de um pedido grava `dsr.update` na mesma transação (FR-16).

Camada de serviço, com dois casos de uso:

- `PrivacyRequestService.submit`, de `POST /v1/privacy/requests`. Qualquer pessoa pode
  abrir um pedido. `controllers/privacy.py` monta o serviço por pedido e passa o `user_id`
  quando há sessão válida, para ligar o pedido ao membro.
- `PrivacyQueueService`, de `GET` e `PATCH /v1/admin/privacy/requests`. Montado em
  `core/container.py:get_privacy_queue_service`. `controllers/admin_privacy.py` confere o
  admin com `require_admin` antes de chamar.

Usa `PrivacyRequestRepository`, `AuditRepository` e `RateLimitRepository`, e as regras de
`domain/privacy.py`. A métrica `atrium_dsr_open{overdue}` não é contada aqui: o `/metrics`
lê os pedidos abertos do banco (`ops_metrics.py`).
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.auth import bucket_key
from app.domain.errors import Conflict, NotFound, RateLimited, ValidationFailed
from app.domain.privacy import (
    CLOSED_REQUEST_PAGE,
    DSR_TARGET_TYPE,
    DSR_UPDATE_ACTION,
    PRIVACY_REQUEST_IP_PURPOSE,
    RequestStatus,
    UpdateProblem,
    due_at,
    is_overdue,
    plan_update,
    privacy_rate_decision,
    privacy_window_start,
    transition_reason,
    validate_request,
)
from app.models.data_subject_request import DataSubjectRequest
from app.ports.clock import Clock
from app.prompts.privacy import (
    NOTE_INVALID,
    NOTE_REQUIRED,
    NOTE_TOO_LONG,
    RATE_LIMITED,
    REQUEST_CLOSED,
    REQUEST_INVALID,
    REQUEST_NOT_FOUND,
    STATUS_INVALID,
    UPDATE_INVALID,
    field_message,
)
from app.repositories.audit import AuditRepository
from app.repositories.privacy_requests import PrivacyRequestRepository
from app.repositories.rate_limits import RateLimitRepository


@dataclass(frozen=True, slots=True)
class PrivacyRequestRecord:
    """O pedido recém-aberto, como a resposta 201 o devolve. Sem e-mail nem descrição."""

    id: UUID
    request_type: str
    status: str
    received_at: datetime
    due_at: datetime


class PrivacyRequestService:
    """Abre pedidos de titular pelo canal público (seção 11.5).

    `hmac_key` é a `RATE_LIMIT_HMAC_KEY` do balde de 5 pedidos por IP no dia.
    """

    def __init__(self, *, database_url: str, clock: Clock, hmac_key: str) -> None:
        self._database_url = database_url
        self._clock = clock
        self._hmac_key = hmac_key

    async def submit(
        self,
        *,
        contact_email: str,
        request_type: str,
        description: str,
        client_ip: str,
        user_id: UUID | None,
    ) -> PrivacyRequestRecord:
        """Valida, aplica o limite de 5 por IP no dia e grava com prazo de 15 dias.

        1. Valida no domínio: um e-mail só, sem caractere que vire cópia num `mailto:`, tipo
           conhecido e descrição de 1 a 2.000 caracteres sem caractere de controle. Falha
           responde 422 com `field_errors` e não gasta o balde.
        2. Numa transação, conta o pedido no balde do IP e, se não passou do limite, grava
           com `status = open` e `due_at` 15 dias corridos depois.
        3. Com o limite estourado, levanta `RateLimited` (429) depois que a transação
           confirmou o contador.

        `user_id` liga o pedido à conta. Ele vira nulo se a conta for excluída, porque o
        pedido é guardado 2 anos depois de fechado (seção 8.1).
        """
        if not self._hmac_key:
            raise RuntimeError("RATE_LIMIT_HMAC_KEY vazio.")
        # 1. Validação antes do balde.
        draft, issues = validate_request(
            contact_email=contact_email,
            request_type=request_type,
            description=description,
        )
        if draft is None:
            raise ValidationFailed(
                REQUEST_INVALID,
                field_errors={field: field_message(field) for field in issues},
            )
        now = self._clock.now()
        window = privacy_window_start(now)
        # O IP só entra no HMAC com o sal do dia. O banco nunca vê o IP cru (seção 8.1).
        key = bucket_key(
            purpose=PRIVACY_REQUEST_IP_PURPOSE,
            subject=client_ip,
            day=now.astimezone(UTC).date(),
            key=self._hmac_key,
        )
        # 2. Contador e pedido na mesma transação.
        async with open_session(self._database_url) as session, UnitOfWork(session):
            count = await RateLimitRepository(session).increment(key, window)
            decision = privacy_rate_decision(count=count, now=now, window_start=window)
            row = None
            if not decision.limited:
                row = await PrivacyRequestRepository(session).insert(
                    user_id=user_id,
                    contact_email=draft.contact_email,
                    request_type=draft.request_type,
                    description=draft.description,
                    status=RequestStatus.OPEN.value,
                    received_at=now,
                    due_at=due_at(now),
                )
                record = PrivacyRequestRecord(
                    id=row.id,
                    request_type=row.request_type,
                    status=row.status,
                    received_at=row.received_at,
                    due_at=row.due_at,
                )
        # 3. O sexto pedido do IP no dia responde 429.
        if row is None:
            raise RateLimited(RATE_LIMITED, retry_after_seconds=decision.retry_after_seconds)
        return record


@dataclass(frozen=True, slots=True)
class QueueItem:
    """Um pedido na fila do admin (seção 12).

    `overdue` é calculado com o mesmo instante da leitura: aberto com o prazo vencido.
    `linked_account` diz que o pedido veio com sessão e a conta ainda existe, porque a
    exclusão da conta deixa `user_id` nulo.
    """

    id: UUID
    request_type: str
    status: str
    contact_email: str
    description: str
    received_at: datetime
    due_at: datetime
    closed_at: datetime | None
    resolution_note: str | None
    overdue: bool
    linked_account: bool


@dataclass(frozen=True, slots=True)
class Queue:
    """A fila e o instante usado para decidir quais pedidos estão atrasados."""

    generated_at: datetime
    requests: list[QueueItem]


# Problema do domínio, campo de `field_errors` e mensagem em português.
_UPDATE_FIELD = {
    UpdateProblem.STATUS_INVALID: ("status", STATUS_INVALID),
    UpdateProblem.NOTE_TOO_LONG: ("resolution_note", NOTE_TOO_LONG),
    UpdateProblem.NOTE_INVALID: ("resolution_note", NOTE_INVALID),
    UpdateProblem.NOTE_REQUIRED: ("resolution_note", NOTE_REQUIRED),
}


class PrivacyQueueService:
    """Fila de pedidos de titular do admin. Seções 11.5, 12 e 15.5 do SDD."""

    def __init__(self, *, database_url: str, clock: Clock) -> None:
        self._database_url = database_url
        self._clock = clock

    async def queue(self) -> Queue:
        """Abertos primeiro, do prazo mais antigo ao mais novo, então os atrasados no topo.

        Depois vêm os 50 fechados mais recentes.

        Uma consulta só lê os abertos e os fechados, numa transação curta de leitura, então
        um pedido fechado durante a leitura não aparece duas vezes.
        """
        now = self._clock.now()
        async with open_session(self._database_url) as session, UnitOfWork(session):
            rows = await PrivacyRequestRepository(session).queue(closed_limit=CLOSED_REQUEST_PAGE)
            items = [_item(row, now) for row in rows]
        return Queue(generated_at=now, requests=items)

    async def update(
        self,
        *,
        admin_id: UUID,
        request_id: UUID,
        status: str,
        resolution_note: str | None,
    ) -> QueueItem:
        """Muda o status e a nota. Uma mudança real grava `dsr.update` na mesma transação.

        1. Trava a linha do pedido (`SELECT ... FOR UPDATE`), para dois admins não fecharem
           o mesmo pedido ao mesmo tempo. Inexistente responde 404.
        2. Aplica as regras de `domain/privacy.py:plan_update`: um pedido fechado não muda
           mais (409); status desconhecido, nota longa, nota com caractere de controle ou
           fechamento sem nota respondem 422 em `field_errors`.
        3. Sem mudança de status nem de nota, devolve o item sem gravar e sem auditoria.
        4. Com mudança, grava, preenche `closed_at` ao fechar e audita só a troca de status
           (`open->in_progress`), nunca a nota nem o e-mail.

        Os erros sobem de dentro da transação e a desfazem; nada foi gravado antes deles.
        """
        now = self._clock.now()
        async with open_session(self._database_url) as session, UnitOfWork(session):
            repository = PrivacyRequestRepository(session)
            # 1.
            row = await repository.lock(request_id)
            if row is None:
                raise NotFound(REQUEST_NOT_FOUND)
            previous = row.status
            # 2.
            change, problem = plan_update(
                current_status=row.status,
                current_note=row.resolution_note,
                status=status,
                resolution_note=resolution_note,
                now=now,
            )
            if problem is UpdateProblem.CLOSED:
                raise Conflict(REQUEST_CLOSED)
            if change is None:
                field, message = _UPDATE_FIELD[problem or UpdateProblem.STATUS_INVALID]
                raise ValidationFailed(UPDATE_INVALID, field_errors={field: message})
            # 3 e 4. Repetir o mesmo status e a mesma nota não grava outro evento.
            if change.changed:
                row = await repository.apply(
                    row,
                    status=change.status,
                    resolution_note=change.resolution_note,
                    closed_at=change.closed_at,
                )
                await AuditRepository(session).record(
                    actor_user_id=admin_id,
                    action=DSR_UPDATE_ACTION,
                    target_type=DSR_TARGET_TYPE,
                    target_id=row.id,
                    reason=transition_reason(previous, change.status),
                    created_at=now,
                )
            item = _item(row, now)
        return item


def _item(row: DataSubjectRequest, now: datetime) -> QueueItem:
    """Converte a linha do ORM no item da fila, ainda dentro da transação."""
    return QueueItem(
        id=row.id,
        request_type=row.request_type,
        status=row.status,
        contact_email=row.contact_email,
        description=row.description,
        received_at=row.received_at,
        due_at=row.due_at,
        closed_at=row.closed_at,
        resolution_note=row.resolution_note,
        overdue=is_overdue(status=row.status, due_at=row.due_at, now=now),
        linked_account=row.user_id is not None,
    )
