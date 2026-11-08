"""Cópias da página da conta. Seção 15.5 do SDD.

Camada de prompts. `AccountService` (`app/services/account.py`) usa as mensagens de erro de
`PATCH /v1/me`, `PUT /v1/me/consents/{purpose}` e `DELETE /v1/me`; `app/controllers/account.py`
usa o nome do arquivo da exportação. A página da conta mostra a `message` do envelope de erro
e os `field_errors` junto dos campos. Seções 11.5 e 12 do SDD.
"""

# Erro de campo de `visitor_type` ou `visit_reason` sem a personalização ativa.
PERSONALIZATION_REQUIRED = "Ative a personalização em Privacidade para informar este campo."
# 422 de `PUT /v1/me/consents` para maioridade, revogação dos Termos ou finalidade desconhecida.
PURPOSE_NOT_CHANGEABLE = "Este consentimento não pode ser alterado por aqui."
# 403 de `DELETE /v1/me` para um admin (seção 10.5).
ADMIN_CANNOT_DELETE = "Um admin não pode excluir a própria conta pela API."
# `message` do 422 de `PATCH /v1/me`; cada campo traz a própria mensagem em `field_errors`.
PROFILE_NOT_CHANGED = "Não foi possível salvar o perfil."
# 404 quando a conta da sessão não existe mais.
USER_NOT_FOUND = "Não encontrei esta conta."
# Nome do arquivo no `Content-Disposition` de `GET /v1/me/export`.
EXPORT_FILENAME = "atrium-meus-dados.json"
