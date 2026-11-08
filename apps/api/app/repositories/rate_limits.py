"""Janela fixa de limite de taxa. A chave não contém o IP cru. Seção 8.1.

Camada de repositório (seção 6.2 do SDD). Grava `rate_limit_windows`. Quem usa: o
`AuthService` (login por e-mail e por IP), o `RegistrationService` (cadastro por IP), o
`ConversationService` (perguntas e diagnóstico), o `DocumentAdminService` (uploads) e o
`PrivacyRequestService` (pedidos de titular). A chave do balde vem de `bucket_key` e o início
da janela, de `fixed_window_start`, ambos do domínio. Os limites estão na seção 10.4 do SDD.
"""

from datetime import datetime

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rate_limit_window import RateLimitWindow


class RateLimitRepository:
    """Contador atômico por balde e janela."""

    def __init__(self, session: AsyncSession) -> None:
        """Usa a sessão aberta pelo serviço, sem abrir transação própria."""
        self._session = session

    async def increment(self, bucket_key: str, window_start: datetime) -> int:
        """Soma 1 ao contador do balde na janela e devolve o total, já com este pedido.

        O `insert` do dialeto PostgreSQL gera um upsert:
        `INSERT ... ON CONFLICT (bucket_key, window_start) DO UPDATE SET count = count + 1
        RETURNING count`. O primeiro pedido da janela cria a linha com 1, e os seguintes somam
        na mesma linha. O `ON CONFLICT` usa a chave primária, e o UPDATE trava a linha: dois
        pedidos simultâneos não leem o mesmo valor, então nenhum escapa do limite. Quem decide
        se o total passou do limite é o domínio.
        """
        statement = (
            insert(RateLimitWindow)
            .values(
                bucket_key=bucket_key,
                window_start=window_start,
                count=1,
            )
            .on_conflict_do_update(
                index_elements=[RateLimitWindow.bucket_key, RateLimitWindow.window_start],
                # Dentro do `DO UPDATE`, `RateLimitWindow.count` é o valor já gravado.
                set_={"count": RateLimitWindow.count + 1},
            )
            .returning(RateLimitWindow.count)
        )
        value = await self._session.scalar(statement)
        return int(value or 0)
