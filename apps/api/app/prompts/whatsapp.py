"""Textos do canal WhatsApp, em português. Seções 29.5, 30.5, 30.6 e 30.9 do SDD.

Camada de prompts. `services/whatsapp.py` monta as mensagens com estes textos, e
`domain/whatsapp.py` põe o rótulo "Atrium (IA)" ou "Equipe do Harborlight" na frente. Os
títulos dos botões têm até 20 caracteres, o limite da Meta, e um teste confere.
"""

from app.domain.handoff import CloseReason
from app.domain.whatsapp import Button

MESA = "(555) 014-2600"

# O aviso antes da primeira resposta e a cada versão nova dos documentos (seção 30.9.4).
NOTICE = (
    "Olá! Eu sou o Atrium, o assistente com inteligência artificial do Harborlight General "
    "Hospital. Respondo com as informações publicadas pelo hospital e posso errar.\n\n"
    "Não envie dados de saúde, fotos de exames nem documentos. Eu não dou orientação médica. "
    "Em uma emergência, procure o pronto-socorro na Harbor Street.\n\n"
    "Sua conversa é apagada 30 dias depois da sua última mensagem. Para apagar antes, envie "
    "APAGAR DADOS. Aviso de Privacidade: {privacy_url}"
)

# Respostas fixas da seção 30.6.
MEDIA = (
    "Por enquanto eu só leio mensagens de texto. Escreva sua pergunta, por favor. Não envie "
    "fotos de exames nem documentos."
)
RATE_LIMITED = "Recebi muitas mensagens em pouco tempo. Tente de novo em alguns minutos."
EMPTY = "Não entendi a mensagem. Escreva sua pergunta em texto, por favor."
UNKNOWN_BUTTON = "Esse botão não vale mais. Escreva sua pergunta, por favor."

# Oferta e confirmação do atendimento (seção 30.5).
OFFER = "Quer falar com uma pessoa da equipe?"
CONFIRM = (
    "Uma pessoa da equipe de atendimento do Harborlight vai ler esta conversa para continuar "
    "daqui.\n\n"
    "A equipe não vê seu número nem seu nome do WhatsApp. O que você escrever para a equipe não "
    "vai para a IA, e a mensagem passa pelo WhatsApp, da Meta, como toda mensagem deste canal."
    "\n\n"
    "Não compartilhe dados de saúde, documentos ou dados de outras pessoas. A equipe não dá "
    "orientação médica e não informa se alguém está internado.\n\n"
    "As mensagens do atendimento são apagadas com esta conversa, 30 dias depois da sua última "
    "mensagem."
)
OFFER_DECLINED = "Tudo bem. Você pode continuar perguntando ao Atrium."
BUSY = (
    "A fila está cheia agora. Tente de novo em alguns minutos ou ligue para a mesa telefônica "
    f"no {MESA}."
)
CLOSED_AVAILABILITY = (
    f"Ninguém da equipe está disponível agora. Você pode ligar para a mesa telefônica no {MESA}."
)
BLOCKED = (
    "O atendimento por uma pessoa não está disponível para você agora. Ligue para a mesa "
    f"telefônica no {MESA}."
)
NOT_OFFERED = "O atendimento por uma pessoa não está disponível para esta resposta."
QUEUED = "Você está na fila. Posição {position}. Para sair, envie ENCERRAR."
RETURNED = "Outra pessoa da equipe vai continuar o atendimento. Posição na fila: {position}."
ASSIGNED = "Uma pessoa da equipe do Harborlight vai responder por aqui."
NO_HANDOFF = "Você não está em atendimento com a equipe. Escreva sua pergunta ao Atrium."
CONTINUE = "Você pode continuar perguntando ao Atrium."

# Os textos de encerramento da seção 29.5, iguais aos da tela.
_STAFF_CLOSED = "Atendimento encerrado pela equipe."
_NOBODY = (
    f"Ninguém da equipe conseguiu responder agora. Você pode ligar para a mesa telefônica no "
    f"{MESA}."
)
CLOSE_TEXTS: dict[str, str] = {
    CloseReason.RESOLVED: _STAFF_CLOSED,
    CloseReason.REDIRECTED: _STAFF_CLOSED,
    CloseReason.OUT_OF_SCOPE: _STAFF_CLOSED,
    CloseReason.NO_RESPONSE: _STAFF_CLOSED,
    CloseReason.ABUSIVE: (
        "Atendimento encerrado. O atendimento por uma pessoa fica indisponível para você por "
        "24 horas."
    ),
    CloseReason.VISITOR_CANCELLED: "Você saiu da fila.",
    CloseReason.VISITOR_ENDED: "Você encerrou o atendimento.",
    CloseReason.QUEUE_TIMEOUT: _NOBODY,
    CloseReason.VISITOR_LEFT: _NOBODY,
    CloseReason.SERVICE_CLOSED: _NOBODY,
    CloseReason.INACTIVITY: "Atendimento encerrado por falta de mensagens.",
}

# Eliminação pelo comando (seção 30.9.6).
DELETE_CONFIRM = "Quer apagar todas as suas conversas com o Atrium? Isso não pode ser desfeito."
DELETE_DONE = (
    "Pronto, apagamos suas conversas com o Atrium. As mensagens no seu aparelho continuam com você."
)
DELETE_CANCELLED = "Nada foi apagado. Você pode continuar perguntando ao Atrium."

# Títulos dos botões, até 20 caracteres.
BUTTON_TITLES: dict[str, str] = {
    Button.OFFER_YES: "Falar com uma pessoa",
    Button.OFFER_NO: "Não, obrigado",
    Button.CONFIRM_YES: "Chamar a equipe",
    Button.CONFIRM_NO: "Agora não",
    Button.DELETE_YES: "Apagar",
    Button.DELETE_NO: "Cancelar",
}

# Motivo de não entrega mostrado no console (seção 30.5).
DELIVERY_ERRORS: dict[int, str] = {
    131047: "A janela de 24 horas do WhatsApp terminou.",
    130497: "A Meta bloqueou o envio para o país deste número. Avise quem opera.",
    190: "O token do WhatsApp não vale mais. Avise quem opera.",
}
DELIVERY_ERROR_DEFAULT = "O WhatsApp não entregou esta mensagem."

# Erros das rotas do webhook (seção 30.10). Quem lê é a Meta, não o visitante.
BAD_SIGNATURE = "Assinatura do webhook inválida."
BAD_VERIFY_TOKEN = "Token de verificação inválido."
TOO_LARGE = "O corpo do webhook passa de 3 MB."
TOO_MANY = "Assinaturas inválidas demais em pouco tempo."


def delivery_error_text(error_code: int | None) -> str:
    """O motivo da não entrega mostrado no console, sem detalhe técnico."""
    if error_code is None:
        return DELIVERY_ERROR_DEFAULT
    return DELIVERY_ERRORS.get(error_code, DELIVERY_ERROR_DEFAULT)
