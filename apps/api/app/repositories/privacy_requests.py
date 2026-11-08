"""Pedidos de titular. Seções 8.1 e 12 do SDD.

Camada de repositório (seção 6.2 do SDD). Lê e grava `data_subject_requests`. O
`PrivacyRequestService` grava o pedido do canal público, e o `PrivacyQueueService` lê a fila e
muda o status pelo admin. Devolve as entidades `DataSubjectRequest`, que o serviço lê dentro da
própria transação. Seções 11.5 e 15.5 do SDD.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.privacy import CLOSED_STATUSES, OPEN_STATUSES
from app.models.data_subject_request import DataSubjectRequest


class PrivacyRequestRepository:
    """Consultas do canal do titular e da fila do admin."""

    def __init__(self, session: AsyncSession) -> None:
        """Usa a sessão aberta pelo serviço, sem abrir transação própria."""
        self._session = session

    async def insert(
        self,
        *,
        user_id: UUID | None,
        contact_email: str,
        request_type: str,
        description: str,
        status: str,
        received_at: datetime,
        due_at: datetime,
    ) -> DataSubjectRequest:
        """Grava o pedido e devolve a entidade com o id gerado pelo banco no `flush()`.

        `user_id` é o membro da sessão, ou `None` para um pedido sem sessão.
        """
        row = DataSubjectRequest(
            user_id=user_id,
            contact_email=contact_email,
            request_type=request_type,
            description=description,
            status=status,
            received_at=received_at,
            due_at=due_at,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def queue(self, *, closed_limit: int) -> list[DataSubjectRequest]:
        """Abertos e em andamento, do prazo mais antigo ao mais novo, e os fechados mais recentes.

        Os atrasados têm o prazo mais antigo, então ficam primeiro. Uma consulta só, para os
        abertos e os fechados saírem do mesmo instante do banco: um pedido fechado no meio da
        leitura não aparece duas vezes.

        1. A subconsulta escolhe os `closed_limit` pedidos fechados mais recentes.
        2. A consulta principal pega todos os abertos mais esses fechados.
        3. A ordem põe os abertos antes, pelo prazo, e depois os fechados, pelo fechamento.
        """
        request = DataSubjectRequest
        is_open = request.status.in_(OPEN_STATUSES)
        # 1. `nulls_last()` só protege a ordem: um pedido fechado sempre tem `closed_at`.
        recent_closed = (
            select(request.id)
            .where(request.status.in_(CLOSED_STATUSES))
            .order_by(request.closed_at.desc().nulls_last(), request.id)
            .limit(closed_limit)
        )
        # 2.
        result = await self._session.scalars(
            select(request)
            .where(or_(is_open, request.id.in_(recent_closed)))
            # 3. `case` vira `CASE WHEN ... THEN ... ELSE ... END` no SQL. A primeira chave
            # separa abertos (0) de fechados (1). A segunda ordena os abertos pelo prazo e
            # deixa os fechados nulos no fim. A terceira ordena os fechados pelo fechamento,
            # e as duas últimas só desempatam.
            .order_by(
                case((is_open, 0), else_=1),
                case((is_open, request.due_at), else_=None).asc().nulls_last(),
                request.closed_at.desc().nulls_last(),
                request.received_at,
                request.id,
            )
        )
        return list(result.all())

    async def lock(self, request_id: UUID) -> DataSubjectRequest | None:
        """Lê o pedido com trava de linha, para dois admins não fecharem o mesmo ao mesmo tempo.

        `with_for_update()` gera `SELECT ... FOR UPDATE`: a linha fica travada até o fim da
        transação. O segundo admin espera, lê o pedido já fechado e recebe 409. `None` quando
        o pedido não existe.
        """
        return await self._session.scalar(
            select(DataSubjectRequest)
            .where(DataSubjectRequest.id == request_id)
            .with_for_update()
        )

    async def apply(
        self,
        row: DataSubjectRequest,
        *,
        status: str,
        resolution_note: str | None,
        closed_at: datetime | None,
    ) -> DataSubjectRequest:
        """Muda status, nota e fechamento do pedido travado por `lock`.

        A sessão percebe a mudança dos atributos da entidade, e o `flush()` envia o UPDATE.
        As regras da troca ficam no domínio (`plan_update`).
        """
        row.status = status
        row.resolution_note = resolution_note
        row.closed_at = closed_at
        await self._session.flush()
        return row
