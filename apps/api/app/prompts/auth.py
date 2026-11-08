"""Cópias de autenticação. O erro de login não revela se o e-mail existe.

Camada de prompts. `AuthService` e `BootstrapAdminService` (`app/services/auth.py`), o
`ApiGuardMiddleware`, o tratador de `app/core/errors.py`, o `ConversationService` e os scripts
usam estes textos. E-mail desconhecido, senha errada e limite de login estourado mostram o
mesmo `INVALID_CREDENTIALS` (seção 10.4). Seções 10.3 a 10.5 do SDD.
"""

# A tela de entrar mostra sempre este texto quando o login falha (seção 15.5).
INVALID_CREDENTIALS = "E-mail ou senha incorretos."
# 401 sem sessão válida.
UNAUTHENTICATED = "Entre para continuar."
# 403 de quem não é admin numa rota de admin.
FORBIDDEN = "Você não tem acesso a esta página."
# 403 `bad_origin` do middleware: `Origin` diferente de `WEB_ORIGIN` (seção 10.3).
BAD_ORIGIN = "Não foi possível confirmar a origem deste pedido."
# 403 de um pedido a `/v1` sem o segredo da borda, de quem chama a Railway direto (seção 10.3).
EDGE_FORBIDDEN = "Acesse o Atrium pelo endereço publicado."
# 422 de um corpo que não passa no schema. Não repete o que a pessoa mandou.
VALIDATION = "Não foi possível validar os dados enviados."
# Nome gravado no admin criado pelo script, que não pede nome.
ADMIN_DISPLAY_NAME = "Administrador"
# Mensagens do script `bootstrap_admin`, para quem opera a implantação (seção 10.5). Saem no
# terminal ou no log do pré-deploy.
ADMIN_CREDENTIALS_MISSING = "Defina ADMIN_EMAIL e ADMIN_PASSWORD para criar o primeiro admin."
ADMIN_EMAIL_INVALID = "ADMIN_EMAIL não é um e-mail válido."
ADMIN_PASSWORD_LENGTH = "ADMIN_PASSWORD precisa ter de 12 a 72 caracteres."
ADMIN_NOT_FOUND = "Nenhum admin com esse e-mail."
ADMIN_LAST = "Não é possível remover o último admin."
ADMIN_CREATED = "Admin criado."
ADMIN_EXISTS = "Já existe um admin. ADMIN_EMAIL e ADMIN_PASSWORD foram ignorados."
ADMIN_REMOVED = "Admin removido."
# Os scripts de linha de comando param com esta mensagem antes de abrir o banco.
DATABASE_URL_MISSING = "DATABASE_URL está vazio."
