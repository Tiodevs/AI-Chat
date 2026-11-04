"""Cópias do canal do titular e da retenção. Seções 11.5 e 11.6 do SDD."""

REQUEST_INVALID = "Não foi possível enviar o pedido. Confira os campos."
RATE_LIMITED = "Você fez muitos pedidos hoje. Tente de novo amanhã."
RETENTION_DONE = "Retenção concluída."

_FIELD_MESSAGES = {
    "contact_email": "Digite um e-mail válido para a resposta.",
    "request_type": "Escolha o tipo do pedido.",
    "description": "Descreva o pedido em até 2.000 caracteres.",
}


def field_message(field: str) -> str:
    return _FIELD_MESSAGES.get(field, "Não foi possível usar este valor.")
