"""Janela fixa de limite de taxa. A chave não contém o IP cru. Seção 8.1."""

from datetime import datetime

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rate_limit_window import RateLimitWindow


class RateLimitRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def increment(self, bucket_key: str, window_start: datetime) -> int:
        statement = (
            insert(RateLimitWindow)
            .values(
                bucket_key=bucket_key,
                window_start=window_start,
                count=1,
            )
            .on_conflict_do_update(
                index_elements=[RateLimitWindow.bucket_key, RateLimitWindow.window_start],
                set_={"count": RateLimitWindow.count + 1},
            )
            .returning(RateLimitWindow.count)
        )
        value = await self._session.scalar(statement)
        return int(value or 0)
