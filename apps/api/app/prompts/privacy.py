"""Cópias do canal do titular, da fila do admin e da retenção. Seções 11.5, 11.6 e 12."""

REQUEST_INVALID = "Não foi possível enviar o pedido. Confira os campos."
RATE_LIMITED = "Você fez muitos pedidos hoje. Tente de novo amanhã."
RETENTION_DONE = "Retenção concluída."
REQUEST_NOT_FOUND = "Não encontramos este pedido."
REQUEST_CLOSED = "Este pedido já foi fechado e não muda mais."
UPDATE_INVALID = "Não foi possível atualizar o pedido. Confira os campos."
STATUS_INVALID = "Escolha um status válido."
NOTE_TOO_LONG = "Escreva a nota de resolução em até 2.000 caracteres."
NOTE_INVALID = "A nota tem caracteres que não podem ser gravados. Use só texto."
NOTE_REQUIRED = "Escreva a nota de resolução para concluir ou recusar o pedido."

_FIELD_MESSAGES = {
    "contact_email": "Digite um e-mail válido para a resposta, só com letras, números e . _ + -.",
    "request_type": "Escolha o tipo do pedido.",
    "description": "Descreva o pedido em até 2.000 caracteres, só com texto.",
}


def field_message(field: str) -> str:
    return _FIELD_MESSAGES.get(field, "Não foi possível usar este valor.")
