"""Canal do titular. Seções 10.4 e 11.5 do SDD."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.auth import bucket_key
from app.domain.errors import RateLimited, ValidationFailed
from app.domain.privacy import (
    PRIVACY_REQUEST_IP_PURPOSE,
    RequestStatus,
    due_at,
    privacy_rate_decision,
    privacy_window_start,
    validate_request,
)
from app.ports.clock import Clock
from app.prompts.privacy import RATE_LIMITED, REQUEST_INVALID, field_message
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
