"""Cópias do canal do titular, da fila do admin e da retenção. Seções 11.5, 11.6 e 12.

Camada de prompts. `PrivacyRequestService` e `PrivacyQueueService` (`app/services/privacy.py`)
usam os erros; o script `retention` imprime `RETENTION_DONE`. A página Privacy e a fila do
admin mostram a `message` do envelope e os `field_errors` junto dos campos.
"""

# `message` do 422 de `POST /v1/privacy/requests`; os campos usam `field_message`.
REQUEST_INVALID = "Não foi possível enviar o pedido. Confira os campos."
# 429 do sexto pedido do mesmo IP no dia (seção 10.4).
RATE_LIMITED = "Você fez muitos pedidos hoje. Tente de novo amanhã."
# Linha final do script de retenção.
RETENTION_DONE = "Retenção concluída."
# 404 e 409 do `PATCH` do admin.
REQUEST_NOT_FOUND = "Não encontramos este pedido."
REQUEST_CLOSED = "Este pedido já foi fechado e não muda mais."
# `message` do 422 do `PATCH`, e um erro de campo por `UpdateProblem`.
UPDATE_INVALID = "Não foi possível atualizar o pedido. Confira os campos."
STATUS_INVALID = "Escolha um status válido."
NOTE_TOO_LONG = "Escreva a nota de resolução em até 2.000 caracteres."
NOTE_INVALID = "A nota tem caracteres que não podem ser gravados. Use só texto."
NOTE_REQUIRED = "Escreva a nota de resolução para concluir ou recusar o pedido."

# Texto de cada campo inválido do pedido. Os limites repetem `app/domain/privacy.py`. O texto
# do e-mail cita `. _ + -`, mas depois do `@` a regra aceita só letras, números, hífen e ponto.
_FIELD_MESSAGES = {
    "contact_email": "Digite um e-mail válido para a resposta, só com letras, números e . _ + -.",
    "request_type": "Escolha o tipo do pedido.",
    "description": "Descreva o pedido em até 2.000 caracteres, só com texto.",
}


def field_message(field: str) -> str:
    """Mensagem do campo inválido, ou uma genérica para um campo sem texto próprio."""
    return _FIELD_MESSAGES.get(field, "Não foi possível usar este valor.")
