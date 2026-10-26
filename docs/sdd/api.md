# API HTTP

Parte da [especificação do Atrium](../sdd.md). A numeração das seções é a do documento completo.

## 12. API HTTP

O prefixo da API é `/v1`. O navegador chama `/backend/v1/...`. Os corpos são JSON, salvo uploads. Os erros usam uma forma só:

```json
{
  "error": {
    "code": "not_in_corpus",
    "message": "I don't have that in Harborlight's published information.",
    "request_id": "01J..."
  }
}
```

Erros de validação usam `validation_error` e HTTP 422. Falhas de autorização usam `forbidden` e HTTP 403. Sessões ausentes usam `unauthenticated` e HTTP 401. Origem inválida usa `bad_origin` e HTTP 403. Orçamento estourado usa `degraded` e HTTP 503.

| Método e caminho | Quem | Comportamento |
|---|---|---|
| `GET /health` | Qualquer um | O processo está no ar. Não toca no banco. |
| `GET /ready` | Qualquer um | Banco responde, `vector` está instalada e a dimensão confere. |
| `GET /v1/legal/versions` | Qualquer um | Versão vigente dos Termos e do Aviso |
| `GET /v1/diagnostics/stream` | Qualquer um, limitado | Emite três eventos SSE com 1 segundo de intervalo. Serve para o teste de fumaça do fluxo pelo rewrite. |
| `POST /v1/conversations` | Visitante | Cria uma conversa para a sessão ou para a chave de convidado. |
| `GET /v1/conversations` | Membro | Lista as conversas do membro. |
| `GET /v1/conversations/{id}` | Dono | Devolve mensagens e citações. |
| `POST /v1/conversations/{id}/messages` | Dono | `{ "text", "client_message_id" }`, texto com até 1.000 caracteres. Responde `text/event-stream`. |
| `POST /v1/messages/{id}/feedback` | Dono | `{ "rating": 1 }` ou `{ "rating": -1 }`. Uma vez por mensagem. |
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

