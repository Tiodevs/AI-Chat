"""Eventos de auditoria. Seção 8.1 do SDD.

Camada de repositório (seção 6.2 do SDD). Grava em `audit_events`. Os serviços de documentos,
qualidade do admin, fila de titular e conta chamam `record` na mesma transação da ação
auditada: a ação e o evento ficam gravados juntos, ou nenhum dos dois. Seção 11.8 do SDD.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_event import AuditEvent


class AuditRepository:
    """Acrescenta eventos de auditoria à transação do serviço."""

    def __init__(self, session: AsyncSession) -> None:
        """Usa a sessão aberta pelo serviço, sem abrir transação própria."""
        self._session = session

    async def record(
        self,
        *,
        actor_user_id: UUID,
        action: str,
        target_type: str,
        target_id: UUID,
        created_at: datetime,
        reason: str | None = None,
    ) -> None:
        """Grava um evento, como `document.upload` ou `identity.reveal`.

        `flush()` manda o INSERT ao banco na hora, sem commit. Um erro do banco aparece aqui,
        dentro da transação do serviço, e o commit continua sendo da `UnitOfWork`.
        """
        self._session.add(
            AuditEvent(
                actor_user_id=actor_user_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                reason=reason,
                created_at=created_at,
            )
        )
        await self._session.flush()
