"""Cópias da conversa. Texto visível ao visitante, em português.

Camada de prompts. `ConversationService` (`app/services/conversations.py`) usa estes textos
nos erros das rotas de conversa, de feedback e do fluxo de diagnóstico; `InsightsService`
reaproveita `CONVERSATION_NOT_FOUND`. A tela mostra a `message` do envelope de erro, e
`STREAM_FAILED` chega no evento `error` do SSE (seção 7.1). Seções 10.4 e 12 do SDD.
"""

# 409 de um reenvio com o mesmo `client_message_id`; o envelope leva `message_id`.
DUPLICATE_MESSAGE = "Esta mensagem já foi enviada."
# 409 do segundo feedback na mesma resposta: o feedback vale uma vez (seção 12).
DUPLICATE_FEEDBACK = "Esta resposta já foi avaliada."
# 404 de conversa ou mensagem inexistente, e também de quem não é o dono: a resposta é a
# mesma, para não revelar que o id existe (Etapa 15.1, seção 29.8).
CONVERSATION_NOT_FOUND = "Não encontrei esta conversa."
MESSAGE_NOT_FOUND = "Não encontrei esta mensagem."
# 429 das perguntas e do fluxo de diagnóstico (seção 10.4).
RATE_LIMITED = "Muitas perguntas em pouco tempo. Espere um pouco e tente de novo."
DIAGNOSTICS_RATE_LIMITED = "Muitas verificações em pouco tempo. Espere um pouco e tente de novo."
# 422 de feedback numa mensagem do visitante.
FEEDBACK_NOT_ASSISTANT = "Só uma resposta do assistente pode ser avaliada."
# Texto do evento `error` quando o fluxo quebra depois do `meta` (seção 7.1).
STREAM_FAILED = "Não foi possível concluir a resposta."
