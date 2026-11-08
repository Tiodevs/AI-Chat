"""Feedback que não sai do processo. Testes e ambiente sem LangSmith.

Implementa a porta `FeedbackSink` (`app.ports.feedback`, seção 17). Quem usa:
`feedback_sink_for` em `langsmith_tracing`, quando o rastreamento está desligado ou sem chave,
e o `ConversationService`, como padrão quando ninguém injeta um coletor.
"""

from uuid import UUID


class NoopFeedbackSink:
    """Recebe o feedback do visitante e o descarta."""

    async def record(self, run_id: UUID, key: str, score: float) -> None:
        """Não faz nada. A nota continua gravada no banco pelo serviço."""
        return
