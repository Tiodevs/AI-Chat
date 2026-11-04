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

`POST /v1/auth/login` recebe `{ "email", "password" }` e, no sucesso, devolve o mesmo perfil de `GET /v1/me` e define `atrium_session`. O perfil não contém `password_hash`. `needs_legal_acceptance` é verdadeiro quando não há consentimento vigente de `terms_and_privacy_notice` para a `LEGAL_DOCUMENT_VERSION`. `POST /v1/auth/logout` responde 204 e revoga a sessão. `GET /v1/legal/versions` devolve `{ "terms", "privacy_notice", "privacy_contact_email" }`. As duas versões são iguais à constante. `privacy_contact_email` vem de `PRIVACY_CONTACT_EMAIL` e é `null` quando a variável está vazia. A página Privacy o publica como contato do encarregado. A autorização de admin é provada por `GET /v1/admin/probe`, fora do contrato público, até as rotas de admin da tabela.

| Método e caminho | Quem | Comportamento |
|---|---|---|
| `GET /health` | Qualquer um | O processo está no ar. Não toca no banco. |
| `GET /ready` | Qualquer um | Banco responde, `vector` está instalada e a dimensão confere. |
| `GET /v1/legal/versions` | Qualquer um | Versão vigente dos Termos e do Aviso |
| `GET /v1/diagnostics/stream` | Qualquer um, limitado | Emite três eventos `tick`, com `{ "index": 1 }`, `{ "index": 2 }` e `{ "index": 3 }`, um por segundo. O limite é 60 por hora por IP. |
| `POST /v1/conversations` | Visitante | Cria uma conversa para a sessão válida ou, sem sessão, para a chave de convidado. Devolve `{ "id", "created_at" }`. |
| `GET /v1/conversations` | Membro ou admin | Lista as conversas desse usuário, da mais recente para a mais antiga: `{ "conversations": [ { "id", "created_at", "first_question" } ] }`. `first_question` é a primeira pergunta gravada da conversa, ou `null`. A aba Conversas da conta a mostra. |
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
| `PATCH /v1/me` | Membro ou admin | Correção do perfil. Só os campos enviados mudam: `full_name`, `phone`, `visitor_type` e `visit_reason`, com as regras da seção 8.5. `null` limpa um opcional. O e-mail não muda por aqui. `visitor_type` e `visit_reason` exigem a personalização ativa. Erros de campo voltam em `field_errors`. Devolve o mesmo perfil de `GET /v1/me`. |
| `GET /v1/me/export` | Membro ou admin | Exportação JSON da seção 11.5, com `Content-Disposition: attachment`. Traz `exported_at`, `profile`, `consents` e `conversations` com mensagens, citações (índice, título e seção) e o feedback de cada mensagem. Não traz hashes, ids de chunk nem de rastro. |
| `GET /v1/me/consents` | Membro ou admin | `{ "current", "history" }`. `current` tem um item por finalidade, com `granted`, a versão e a data. `history` tem todas as linhas, da mais nova para a mais antiga. |
| `PUT /v1/me/consents/{purpose}` | Membro ou admin | `{ "granted": true }` ou `{ "granted": false }`. Vale para `profile_personalization` e `quality_improvement`. Conceder cria uma linha na versão vigente, com `source = account`. Revogar grava `revoked_at` e, na personalização, apaga `visitor_type` e `visit_reason` na mesma transação. `terms_and_privacy_notice` só aceita `true`, e é assim que o membro aceita a versão nova dos documentos. `age_18_plus` e finalidades desconhecidas respondem 422. Cada mudança grava `consent.change`. |
| `DELETE /v1/me` | Membro ou admin | Exclui a conta e responde 204, apagando o cookie. Um admin recebe 403. |
| `POST /v1/privacy/requests` | Qualquer um, limitado | `{ "contact_email", "request_type", "description" }`, descrição com até 2.000 caracteres. Responde 201 com `{ "id", "request_type", "status", "received_at", "due_at" }`, `status = open` e `due_at` 15 dias corridos depois. Com sessão válida, o pedido guarda o `user_id`. Erros de campo voltam em `field_errors`. O sexto pedido do mesmo IP no dia responde 429. |
| `GET /v1/admin/overview` | Admin | `?period_days=7` ou `30`. Indicadores do período contra o período anterior de mesmo tamanho: `questions`, `answer_rate`, `abstention_rate` e `helpful_rate`, cada um `{ "current", "previous" }`, com `null` sem denominador. Mais `trend` por dia UTC (`date`, `questions`, `answered`), `outcomes`, `intents` e `feedback` em contagens, `funnel` por etapa (`started`, `password_set`, `completed`) com `chat` e `form`, e `budget` (`used_tokens`, `daily_budget`, `ratio`) do dia. |
| `GET /v1/admin/documents` | Admin | `{ "documents" }`, ativos primeiro e depois os arquivados, do mais recente ao mais antigo. Cada item traz `id`, `title`, `slug`, `status`, `created_at`, `updated_at`, `active_version` e `latest_version`. As duas versões trazem `id`, `version`, `filename`, `media_type`, `byte_size`, `ingestion_status`, `error` e `created_at`, e podem ser `null`. |
| `POST /v1/admin/documents` | Admin, limitado | Multipart com `file` e `title` opcional. Responde 201 com o documento, a versão nova em `processing` e `active_version` nula. Grava `document.upload`. |
| `POST /v1/admin/documents/{id}/replace` | Admin, limitado | Multipart com `file`. Responde 202 com o documento. A versão ativa continua a mesma até a nova chegar a `ready`. Grava `document.replace`. |
| `POST /v1/admin/documents/{id}/retry` | Admin, limitado | Sem corpo. Reprocessa o arquivo da última versão, que precisa estar em `failed`, numa versão nova. Responde 202. Grava `document.retry`. |
| `POST /v1/admin/documents/{id}/archive` | Admin | Arquiva e responde 200 com o documento. Arquivar de novo não grava outro evento. Grava `document.archive`. |
| `GET /v1/admin/quality` | Admin | `?period_days=7` ou `30`, `outcome` e `feedback` (`helpful`, `not_helpful`, `none`) opcionais. Devolve `outcomes` e `feedback` do período, de todas as conversas, e até 50 `conversations` com atividade no período, da mais recente para a mais antiga, só de convidados e de membros com `quality_improvement` vigente. Cada uma traz `id`, `subject_kind` (`guest` ou `member`), `pseudonym` (8 caracteres do HMAC de `PSEUDONYM_KEY`), `started_at`, `last_activity_at`, `questions`, `last_outcome`, `helpful` e `not_helpful`. Nunca nome nem e-mail. |
| `GET /v1/admin/conversations/{id}` | Admin | Conversa pseudonimizada com as mensagens: `role`, `content`, `outcome`, `prompt_version`, `model`, `request_id`, `latency_ms`, `run_id`, `trace_url`, citações (índice, título e seção) e `rating`. Grava `conversation.view` na mesma transação. Conversa de membro sem `quality_improvement` vigente responde 404 e não grava nada. |
| `POST /v1/admin/conversations/{id}/reveal` | Admin | `{ "reason" }`, de 10 a 500 caracteres depois de juntar espaços; fora disso, 422 em `field_errors.reason`. Devolve `{ "conversation_id", "full_name", "email" }` e grava `identity.reveal` com o motivo. Conversa de convidado responde 409. Conversa fora do inspetor responde 404. |
| `GET /v1/admin/privacy/requests` | Admin | Fila de pedidos de titular |
| `PATCH /v1/admin/privacy/requests/{id}` | Admin | Status e nota de resolução. Grava `dsr.update`. |
| `GET /metrics` | Bearer `METRICS_TOKEN` | Texto Prometheus. Desligada quando o token não está definido. |

O tipo do upload vem da extensão: `.md` e `.markdown` são `text/markdown`, `.txt` é `text/plain` e `.pdf` é `application/pdf`. O tipo declarado pelo navegador não conta. Texto precisa ser UTF-8 sem byte nulo, e PDF precisa começar com `%PDF-`. Arquivo vazio, acima de 10 MB, de outro tipo ou título acima de 200 caracteres responde 422 com `field_errors` em `file` ou `title`. Sem título, vale o nome do arquivo sem a extensão. O `slug` vem do nome do arquivo, em ASCII com hífens, e ganha `-2`, `-3` quando já existe. Documento inexistente responde 404. Substituir ou tentar de novo um documento arquivado, ou com uma versão em `processing` há menos de 15 minutos, responde 409, e tentar de novo sem falha na última versão também. Upload, substituição e nova tentativa contam no balde de uploads da seção 10.4, que conta a tentativa antes da validação do documento, e o 31º pedido na hora responde 429. A ingestão segue a seção 7.3.

A saudação e as frases modelo do cadastro são cópia fixa em `app/prompts/registration.py`, então a primeira tela não depende do Gemini.

`POST /v1/registration/sessions` responde 201. Os outros pedidos da sessão respondem 200 com `id`, `status`, `path`, `fields`, `field_errors`, `next_step`, `prompt`, `messages` e `expires_at`. `fields` traz `full_name`, `email`, `phone`, `visitor_type` e `visit_reason`. Cada item de `messages` é `{ role, text, created_at }` e não tem senha. O aceite e o formulário devolvem o perfil de `GET /v1/me` e definem `atrium_session`. O formulário aceita `session_id` opcional. No chat, um e-mail já usado volta em `field_errors` e não substitui o e-mail já entendido. No formulário, o mesmo caso responde 409. Conclusão sem os Termos, sem a versão vigente ou sem a maioridade responde 422 e não grava usuário. Um aceite repetido da mesma sessão devolve o mesmo usuário.

