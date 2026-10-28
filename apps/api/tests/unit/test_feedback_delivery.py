"""O feedback chega na execução certa e uma falha não sobe. FR-14."""

import asyncio
from typing import cast
from uuid import UUID, uuid4

import pytest
from langsmith import Client

from app.adapters.langsmith_tracing import LangSmithFeedbackSink
from app.domain.feedback import user_helpful_score
from app.services.conversations import FeedbackNotice, send_user_feedback


class _Sink:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    async def record(self, run_id: UUID, key: str, score: float) -> None:
        self.calls.append((run_id, key, score))


class _Boom:
    async def record(self, run_id: UUID, key: str, score: float) -> None:
        raise RuntimeError("langsmith down")


class _Client:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def create_feedback(
        self,
        run_id: UUID,
        key: str,
        *,
        score: float,
        trace_id: UUID,
    ) -> None:
        self.calls.append((run_id, key, score, trace_id))


def test_helpful_score_maps_rating_to_zero_or_one() -> None:
    assert user_helpful_score(1) == 1.0
    assert user_helpful_score(-1) == 0.0
    with pytest.raises(ValueError):
        user_helpful_score(0)


def test_delivery_uses_user_helpful_on_the_run() -> None:
    sink = _Sink()
    run_id = uuid4()
    asyncio.run(send_user_feedback(sink, FeedbackNotice(run_id=run_id, score=0.0)))
    assert sink.calls == [(run_id, "user_helpful", 0.0)]


def test_delivery_failure_is_logged_and_not_raised(capsys: pytest.CaptureFixture[str]) -> None:
    from app.core.logging import configure_logging

    configure_logging("INFO")
    asyncio.run(send_user_feedback(_Boom(), FeedbackNotice(run_id=uuid4(), score=1.0)))
    output = capsys.readouterr().out
    assert "feedback.langsmith_failed" in output
    assert "langsmith down" not in output


def test_langsmith_sink_posts_feedback_on_that_run() -> None:
    client = _Client()
    sink = LangSmithFeedbackSink(cast(Client, client))
    run_id = uuid4()
    asyncio.run(sink.record(run_id, "user_helpful", 0.0))
    assert client.calls == [(run_id, "user_helpful", 0.0, run_id)]
