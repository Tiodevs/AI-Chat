# API HTTP

Parte da [especificação do Atrium](../sdd.md). A numeração das seções é a do documento completo.

## 12. API HTTP

O prefixo da API é `/v1`. O navegador chama `/backend/v1/...`. Os corpos são JSON, salvo uploads. Os erros usam uma forma só:

```json
{
  "error": {
    "code": "not_in_corpus",
    "message": "Não encontrei isso nas informações publicadas do Harborlight.",
    "request_id": "01J..."
  }
}
```

Erros de validação usam `validation_error` e HTTP 422. Falhas de autorização usam `forbidden` e HTTP 403. Sessões ausentes usam `unauthenticated` e HTTP 401. Origem inválida usa `bad_origin` e HTTP 403. Orçamento estourado usa `degraded` e HTTP 503. Um pedido limitado usa `rate_limited` e HTTP 429, e o objeto `error` inclui `retry_after_seconds`. O 409 de uma mensagem repetida inclui `message_id`, o id da mensagem do visitante já gravada. Erros de campo do cadastro incluem `field_errors`, um objeto de nome de campo para mensagem. Nos outros erros esses campos ficam ausentes.

`POST /v1/auth/login` recebe `{ "email", "password" }` e, no sucesso, devolve o mesmo perfil de `GET /v1/me` e define `atrium_session`. O perfil não contém `password_hash`. `needs_legal_acceptance` é verdadeiro quando não há consentimento vigente de `terms_and_privacy_notice` para a `LEGAL_DOCUMENT_VERSION`. `POST /v1/auth/logout` responde 204 e revoga a sessão. `GET /v1/legal/versions` devolve `{ "terms", "privacy_notice" }`, os dois iguais à constante. A autorização de admin é provada por `GET /v1/admin/probe`, fora do contrato público, até as rotas de admin da tabela.

| Método e caminho | Quem | Comportamento |
|---|---|---|
| `GET /health` | Qualquer um | O processo está no ar. Não toca no banco. |
| `GET /ready` | Qualquer um | Banco responde, `vector` está instalada e a dimensão confere. |
| `GET /v1/legal/versions` | Qualquer um | Versão vigente dos Termos e do Aviso |
| `GET /v1/diagnostics/stream` | Qualquer um, limitado | Emite três eventos `tick`, com `{ "index": 1 }`, `{ "index": 2 }` e `{ "index": 3 }`, um por segundo. O limite é 60 por hora por IP. |
| `POST /v1/conversations` | Visitante | Cria uma conversa para a sessão válida ou, sem sessão, para a chave de convidado. Devolve `{ "id", "created_at" }`. |
| `GET /v1/conversations` | Membro ou admin | Lista as conversas desse usuário, da mais recente para a mais antiga: `{ "conversations": [ { "id", "created_at" } ] }`. |
| `GET /v1/conversations/{id}` | Dono | Devolve `{ "id", "created_at", "messages" }`. Cada mensagem traz `id`, `role`, `content`, `client_message_id`, `citations`, `outcome` e `created_at`. |
| `POST /v1/conversations/{id}/messages` | Dono | `{ "text", "client_message_id" }`, texto com até 1.000 caracteres. Responde `text/event-stream`. |
| `POST /v1/messages/{id}/feedback` | Dono | `{ "rating": 1 }` ou `{ "rating": -1 }`, só numa mensagem do assistente. Uma vez. Devolve `{ "message_id", "rating" }`. |
| `POST /v1/registration/sessions` | Visitante | Começa um cadastro por chat e devolve a saudação. |
| `GET /v1/registration/sessions/{id}` | Quem tem a sessão | Status, campos entendidos, erros e `next_step` |
| `POST /v1/registration/sessions/{id}/messages` | Quem tem a sessão | Turno do chat |
| `PATCH /v1/registration/sessions/{id}/fields` | Quem tem a sessão | Edição direta no cartão de resumo, com as regras do formulário |
| `POST /v1/registration/sessions/{id}/password` | Quem tem a sessão | `{ "password" }` |
| `POST /v1/registration/sessions/{id}/review` | Quem tem a sessão | `{ "accept": true }` ou `{ "accept": false }` |
| `POST /v1/registration/sessions/{id}/acceptance` | Quem tem a sessão | Aceites da seção 7.2. Conclui e define o cookie. |
| `POST /v1/registration/form` | Visitante | Formulário completo, inclusive senha e aceites. `session_id` opcional. |
| `POST /v1/auth/login` | Visitante | E-mail e senha. Define o cookie. |
| `POST /v1/auth/logout` | Membro ou admin | Revoga a sessão. |
| `GET /v1/me` | Membro ou admin | Perfil e se há novo documento legal a aceitar |
| `PATCH /v1/me` | Membro | Correção do perfil |
| `GET /v1/me/export` | Membro | Exportação JSON da seção 11.5 |
| `GET /v1/me/consents` | Membro | Consentimentos vigentes e histórico |
| `PUT /v1/me/consents/{purpose}` | Membro | `{ "granted": true }` ou `{ "granted": false }`. Revogar a personalização apaga `visitor_type` e `visit_reason`. |
| `DELETE /v1/me` | Membro | Exclui a conta. |
| `POST /v1/privacy/requests` | Qualquer um | `{ "contact_email", "request_type", "description" }` |
| `GET /v1/admin/overview` | Admin | Indicadores do painel, com período e comparação com o período anterior |
| `GET /v1/admin/documents` | Admin | Documentos, versão ativa e status de ingestão |
| `POST /v1/admin/documents` | Admin | Upload multipart e título |
| `POST /v1/admin/documents/{id}/replace` | Admin | Arquivo de substituição em multipart |
| `POST /v1/admin/documents/{id}/archive` | Admin | Arquiva. |
| `GET /v1/admin/quality` | Admin | Contagens por desfecho, feedback e conversas recentes, pseudonimizadas |
| `GET /v1/admin/conversations/{id}` | Admin | Conversa pseudonimizada, links de rastro. Grava `conversation.view`. |
| `POST /v1/admin/conversations/{id}/reveal` | Admin | `{ "reason" }`. Devolve a identidade e grava `identity.reveal`. |
| `GET /v1/admin/privacy/requests` | Admin | Fila de pedidos de titular |
| `PATCH /v1/admin/privacy/requests/{id}` | Admin | Status e nota de resolução. Grava `dsr.update`. |
| `GET /metrics` | Bearer `METRICS_TOKEN` | Texto Prometheus. Desligada quando o token não está definido. |

A saudação e as frases modelo do cadastro são cópia fixa em `app/prompts/registration.py`, então a primeira tela não depende do Gemini.

`POST /v1/registration/sessions` responde 201. Os outros pedidos da sessão respondem 200 com `id`, `status`, `path`, `fields`, `field_errors`, `next_step`, `prompt`, `messages` e `expires_at`. `fields` traz `full_name`, `email`, `phone`, `visitor_type` e `visit_reason`. Cada item de `messages` é `{ role, text, created_at }` e não tem senha. O aceite e o formulário devolvem o perfil de `GET /v1/me` e definem `atrium_session`. O formulário aceita `session_id` opcional. No chat, um e-mail já usado volta em `field_errors` e não substitui o e-mail já entendido. No formulário, o mesmo caso responde 409. Conclusão sem os Termos, sem a versão vigente ou sem a maioridade responde 422 e não grava usuário. Um aceite repetido da mesma sessão devolve o mesmo usuário.

