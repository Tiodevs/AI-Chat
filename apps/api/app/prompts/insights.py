"""Cópias da visão geral e da qualidade do admin. Seções 11.8 e 12 do SDD.

Camada de prompts. `InsightsService` (`app/services/insights.py`) usa estes textos nos erros
das rotas `/v1/admin/overview`, `/v1/admin/quality` e do inspetor de conversas. A tela do
admin mostra a `message` do envelope.
"""

# 422 de `period_days` fora de 7 e 30.
PERIOD_INVALID = "Escolha um período de 7 ou 30 dias."
# 422 de um filtro `outcome` ou `feedback` desconhecido.
FILTER_INVALID = "Filtro de qualidade inválido."
# 404 de uma conversa de membro sem o consentimento de melhoria (seção 11.8).
CONVERSATION_HIDDEN = (
    "Esta conversa não está disponível no inspetor. Ela aparece só nos agregados."
)
# 422 do motivo da revelação. Os números repetem `REVEAL_REASON_*` de `app/domain/insights.py`.
REASON_INVALID = "Explique o motivo em 10 a 500 caracteres."
# 409 ao revelar a identidade de uma conversa de convidado.
GUEST_HAS_NO_IDENTITY = "Conversa de convidado não tem identidade para revelar."
