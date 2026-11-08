"""Porta do feedback. Seção 17 do SDD.

Camada de portas. `send_user_feedback` (`app/services/conversations.py`) chama `record` numa
tarefa de fundo, depois de gravar a nota no banco. Os adaptadores são `LangSmithFeedbackSink`
(`app/adapters/langsmith_tracing.py`), que cria o feedback no run da resposta, e
`NoopFeedbackSink`, para os testes e o ambiente sem LangSmith; `feedback_sink_for` escolhe.
Seção 18.4, "Ligação com o produto".
"""

from typing import Protocol
from uuid import UUID


class FeedbackSink(Protocol):
    """Destino do feedback do visitante sobre uma resposta."""

    async def record(self, run_id: UUID, key: str, score: float) -> None:
        """Registra a nota `score` com a chave `key` no run `run_id`.

        Hoje a chave é sempre `user_helpful`, com 1 ou 0. Uma falha não chega ao visitante:
        `send_user_feedback` captura o erro e registra `feedback.langsmith_failed` no log.
        """
        ...
