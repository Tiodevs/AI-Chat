"""Cópias do atendimento humano. Texto visível ao visitante e à equipe, em português.

Camada de prompts. `services/handoff.py`, `services/attendance.py` e o script `attendants`
usam estes textos nos erros da seção 29.10; a tela mostra a `message` do envelope de erro.
Os textos das telas, como o diálogo de confirmação e o compromisso de confidencialidade,
ficam em `apps/web/src/i18n/pt.ts`. Seção 29 do SDD.
"""

# O prefixo do rótulo do atendimento, antes dos 8 caracteres do HMAC (seção 29.9.4).
LABEL_PREFIX = "Visitante"

# 404 de atendimento inexistente, de outra conversa ou que a pessoa não assumiu.
HANDOFF_NOT_FOUND = "Não encontrei este atendimento."
# 409 `handoff_not_offered`: a última resposta não permite chamar a equipe (seção 29.4).
NOT_OFFERED = "O atendimento por uma pessoa não está disponível para esta resposta."
# 409 `handoff_active`: já há atendimento ativo do visitante, ou a pergunta chegou durante um.
ACTIVE_ELSEWHERE = "Você já tem um atendimento com a equipe em outra conversa."
ACTIVE_HERE = "Esta conversa está com a equipe. Escreva para a equipe ou encerre o atendimento."
# 503 `handoff_unavailable`, com o status da disponibilidade.
UNAVAILABLE = "Ninguém da equipe está disponível agora. Ligue para a mesa telefônica."
# 403 `handoff_blocked`: encerramento por abuso nas últimas 24 horas.
BLOCKED = (
    "O atendimento por uma pessoa não está disponível para você agora. Ligue para a mesa "
    "telefônica no (555) 014-2600."
)
# 409 `handoff_closed`: mensagem ou ação num atendimento encerrado.
CLOSED = "Este atendimento já foi encerrado."
# 409 `handoff_taken`: outra pessoa assumiu primeiro.
TAKEN = "Outra pessoa já assumiu este atendimento."
# 409 `attendant_at_capacity`: a pessoa já tem 3 atendimentos.
AT_CAPACITY = "Você já tem 3 atendimentos. Encerre ou devolva um antes de assumir outro."
# 403 `acknowledgement_required`: falta o aceite do compromisso vigente.
ACKNOWLEDGEMENT_REQUIRED = "Aceite o compromisso de confidencialidade antes de assumir."
# 422 do aceite com uma versão que não é a vigente.
WRONG_TERMS_VERSION = "Esta não é a versão vigente do compromisso."
# 422 de texto vazio, longo demais ou com caractere de controle.
INVALID_TEXT = "Escreva uma mensagem de até {max_chars} caracteres."
# 422 de motivo de encerramento fora da lista ou de categoria de remoção desconhecida.
INVALID_REASON = "Escolha um motivo da lista."
INVALID_CATEGORY = "Escolha uma categoria da lista."
# 422 do motivo para ler um encerrado, de 10 a 500 caracteres (seção 29.10).
VIEW_REASON_LENGTH = "Escreva o motivo com 10 a 500 caracteres."
# 409 de ler um atendimento que ainda está ativo.
VIEW_ACTIVE = "Este atendimento ainda está ativo."
# 409 de reenvio do mesmo `client_message_id`.
DUPLICATE = "Esta mensagem já foi enviada."
# 429 dos baldes e dos fluxos (seções 29.6 e 29.8).
RATE_LIMITED = "Muitas mensagens em pouco tempo. Espere um pouco e tente de novo."
REQUEST_RATE_LIMITED = "Muitos pedidos de atendimento em pouco tempo. Tente de novo mais tarde."
STREAMS_LIMITED = "Há conexões demais abertas. Feche outras abas e tente de novo."
# 403 do papel: só a equipe abre o console.
STAFF_ONLY = "Só a equipe de atendimento pode abrir esta página."
# 403 do fluxo aberto a partir de outro site (seção 29.8, CSRF).
CROSS_SITE = "Abra o atendimento pelo próprio Atrium."
# Texto do evento `error` quando a sessão ou a permissão deixam de valer no meio do fluxo.
STREAM_REVOKED = "Sua sessão terminou. Entre de novo para continuar."
STREAM_GONE = "Este atendimento não está mais com você."

# Mensagens do script `attendants` (seção 29.3).
SCRIPT_NOT_FOUND = "Nenhuma conta com este e-mail."
SCRIPT_NOT_ADMIN = "O e-mail de --by precisa ser de um admin."
SCRIPT_REFUSE_ADMIN = "O script não muda uma conta de admin."
SCRIPT_NOT_MEMBER = "Só uma conta de membro vira atendente."
SCRIPT_NOT_ATTENDANT = "Esta conta não é de atendente."
