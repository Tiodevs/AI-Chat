"""Caso de uso da pergunta, sem HTTP. O orçamento vem antes do workflow. Seção 7.1.

Camada de serviço. `QuestionService` roda o pipeline de perguntas sem conversa, sem gravar
mensagens e sem SSE. Quem o usa é o script `scripts/ask.py`, que pergunta ao Gemini de
desenvolvimento pela linha de comando, e o teste `tests/unit/test_budget.py`. O caminho do
navegador é `ConversationService`, em `conversations.py`.

A ordem é a da seção 7.1: confere o orçamento, roda o `QaWorkflow` e soma os tokens. O
serviço não abre transação própria além das do orçamento; a busca do workflow abre a dela.
"""

from collections.abc import Sequence
from typing import Protocol
from uuid import uuid4

from app.ports.budget import TokenBudget
from app.workflows.qa import ConversationTurn, QaResult, degraded_result


class QuestionWorkflow(Protocol):
    """A parte de `QaWorkflow.run` de que este serviço precisa.

    `run` recebe a pergunta, o histórico já lido, o `visitor_type` opcional e o `request_id`,
    e devolve o `QaResult` com desfecho, texto, citações e tokens. O protocolo deixa o teste
    passar um workflow falso sem montar provedores.
    """

    async def run(
        self,
        question: str,
        *,
        history: Sequence[ConversationTurn],
        visitor_type: str | None,
        request_id: str,
    ) -> QaResult: ...


class QuestionService:
    """Pergunta avulsa: orçamento, pipeline e contagem de tokens."""

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
        """Responde uma pergunta e põe o uso no orçamento.

        1. Com o teto do dia alcançado, devolve o resultado `degraded`, com o texto fixo de
           indisponibilidade, sem chamar o workflow.
        2. Roda o workflow. As chamadas ao modelo e ao embedding acontecem aqui, sem
           transação aberta.
        3. Soma os tokens do resultado em `token_usage_days`.

        Diferente de `ConversationService`, este caminho não acompanha o uso parcial: se o
        workflow levanta uma exceção, ela sobe e nada entra no orçamento. Sem `request_id`,
        gera um novo.
        """
        # 1. Orçamento antes de qualquer chamada ao modelo.
        if await self._budget.exceeded():
            return degraded_result()
        # 2. Pipeline completo da seção 7.1.
        result = await self._workflow.run(
            question,
            history=history,
            visitor_type=visitor_type,
            request_id=request_id or str(uuid4()),
        )
        # 3. Os tokens que o adaptador contou nas chamadas desta pergunta.
        await self._budget.record(result.input_tokens, result.output_tokens)
        return result
