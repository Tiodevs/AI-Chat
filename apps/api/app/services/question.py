"""Caso de uso da pergunta, sem HTTP. O orçamento vem antes do workflow. Seção 7.1."""

from collections.abc import Sequence
from typing import Protocol
from uuid import uuid4

from app.ports.budget import TokenBudget
from app.workflows.qa import ConversationTurn, QaResult, degraded_result


class QuestionWorkflow(Protocol):
    async def run(
        self,
        question: str,
        *,
        history: Sequence[ConversationTurn],
        visitor_type: str | None,
        request_id: str,
    ) -> QaResult: ...


class QuestionService:
    def __init__(self, workflow: QuestionWorkflow, budget: TokenBudget) -> None:
        self._workflow = workflow
        self._budget = budget

    async def ask(
        self,
        question: str,
        *,
        history: Sequence[ConversationTurn] = (),
        visitor_type: str | None = None,
        request_id: str | None = None,
    ) -> QaResult:
        if await self._budget.exceeded():
            return degraded_result()
        result = await self._workflow.run(
            question,
            history=history,
            visitor_type=visitor_type,
            request_id=request_id or str(uuid4()),
        )
        await self._budget.record(result.input_tokens, result.output_tokens)
        return result
