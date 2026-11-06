"""Canal do titular e fila do admin. Seções 10.4, 11.5, 12 e 15.5 do SDD.

Mudar o status de um pedido grava `dsr.update` na mesma transação (FR-16).
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
    id: UUID
    request_type: str
    status: str
    received_at: datetime
    due_at: datetime


class PrivacyRequestService:
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
        """Valida, aplica o limite de 5 por IP no dia e grava com prazo de 15 dias."""
        if not self._hmac_key:
            raise RuntimeError("RATE_LIMIT_HMAC_KEY vazio.")
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
        key = bucket_key(
            purpose=PRIVACY_REQUEST_IP_PURPOSE,
            subject=client_ip,
            day=now.astimezone(UTC).date(),
            key=self._hmac_key,
        )
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
        if row is None:
            raise RateLimited(RATE_LIMITED, retry_after_seconds=decision.retry_after_seconds)
        return record


@dataclass(frozen=True, slots=True)
class QueueItem:
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
    generated_at: datetime
    requests: list[QueueItem]


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
        """Muda o status e a nota. Uma mudança real grava `dsr.update` na mesma transação."""
        now = self._clock.now()
        async with open_session(self._database_url) as session, UnitOfWork(session):
            repository = PrivacyRequestRepository(session)
            row = await repository.lock(request_id)
            if row is None:
                raise NotFound(REQUEST_NOT_FOUND)
            previous = row.status
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
