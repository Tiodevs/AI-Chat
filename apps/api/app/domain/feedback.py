"""Nota do visitante no LangSmith. Seção 18.4 do SDD.

Camada de domínio. `ConversationService.submit_feedback` converte a nota gravada com
`user_helpful_score`, e `send_user_feedback` a envia pela porta `FeedbackSink` numa tarefa de
fundo, com a chave `USER_HELPFUL`, no run da resposta (seção 18.4, "Ligação com o produto").
"""

# Chave do feedback no LangSmith. A automação da fila de anotação procura `user_helpful = 0`.
USER_HELPFUL = "user_helpful"


def user_helpful_score(rating: int) -> float:
    """1 vira 1. -1 vira 0. O banco guarda -1 ou 1.

    Levanta `ValueError` para outra nota. O schema do pedido já só aceita 1 ou -1.
    """
    if rating == 1:
        return 1.0
    if rating == -1:
        return 0.0
    raise ValueError("rating must be 1 or -1")
