"""Feedback que não sai do processo. Testes e ambiente sem LangSmith."""

from uuid import UUID


class NoopFeedbackSink:
    async def record(self, run_id: UUID, key: str, score: float) -> None:
        return
