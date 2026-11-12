# schemas

Modelos Pydantic de pedido e resposta da API: a camada de schema, a parte do controlador que descreve o corpo HTTP ([seção 6.2 do SDD](../../../../docs/sdd/arquitetura.md#62-mvc-com-as-camadas-de-que-um-sistema-de-ia-precisa)). O FastAPI gera o OpenAPI a partir deles, e o frontend gera os tipos desse OpenAPI ([seção 6.6](../../../../docs/sdd/arquitetura.md#66-contrato-entre-api-e-frontend)); o contrato de cada rota está na [seção 12](../../../../docs/sdd/api.md#12-api-http).

## Arquivos

| Arquivo | O que faz | Quem usa |
|---|---|---|
| [`__init__.py`](__init__.py) | Docstring do pacote: o papel da camada e por que os comentários de classe ficam em `#` | O pacote |
| [`errors.py`](errors.py) | `ErrorBody` e `ErrorResponse`, o envelope de erro de toda a API | `app.core.errors`, `app.core.middleware` e o `responses=` de cada controlador |
| [`legal.py`](legal.py) | `LegalVersionsResponse`, as versões dos Termos e do Aviso e o contato do encarregado | Controlador `legal` |
| [`auth.py`](auth.py) | `LoginRequest`, `ProfileResponse` e `AdminProbeResponse` | Controladores `auth`, `account`, `registration` e `admin_probe` |
| [`account.py`](account.py) | Correção do perfil, consentimentos e os modelos `Export*` da exportação do titular | Controlador `account` |
| [`conversations.py`](conversations.py) | Pergunta, feedback, criação, lista e leitura de conversas | Controlador `conversations` |
| [`documents.py`](documents.py) | Respostas da gestão de documentos e as funções que convertem a visão do domínio | Controlador `admin_documents` |
| [`insights.py`](insights.py) | Visão geral, qualidade, inspetor e revelação de identidade do admin | Controlador `admin_insights` |
| [`privacy.py`](privacy.py) | Canal público do titular e a fila de pedidos do admin | Controladores `privacy` e `admin_privacy` |
| [`registration.py`](registration.py) | Turnos, senha, revisão, aceite, formulário e a resposta da sessão de cadastro | Controlador `registration` |
| [`handoff.py`](handoff.py) | Pedidos e respostas do atendimento humano: disponibilidade, atendimento do visitante, mensagem, presença, aceite, fila sem conteúdo, detalhe para quem assumiu e a lista de encerrados | Controladores `handoff`, `attendance` e `admin_handoffs` |

## Como ler

Os modelos não têm lógica: leia cada arquivo junto com o controlador que o usa. Os conceitos que ajudam:

- **`BaseModel`.** Cada campo anotado vira um campo validado na entrada e serializado na saída. Um corpo inválido responde 422 antes de o controlador rodar.
- **`model_config = ConfigDict(extra="forbid")`.** Recusa campo desconhecido. Num modelo de resposta, aparece no OpenAPI como `additionalProperties: false`.
- **`Field(min_length=..., max_length=...)`.** Os limites daqui são externos: barram um corpo absurdo com 422 sem `field_errors`. As regras de campo da [seção 8.5](../../../../docs/sdd/arquitetura.md#85-regras-dos-campos) ficam no domínio e voltam em `field_errors`.
- **`Literal[...]`.** Fecha os valores aceitos, como `rating` em `-1` ou `1`, e o OpenAPI e os tipos do frontend passam a listá-los.
- **`field_validator`.** Roda depois do tipo e dos limites do `Field`. Aqui, tira os espaços das pontas do texto.
- **Campo ausente contra `null`.** Nos dois `PATCH` com campos opcionais, o controlador lê só os campos enviados (`exclude_unset=True` ou `model_fields_set`): ausente não muda, e `null` limpa.
- **Docstring vira contrato.** A docstring de um modelo Pydantic vira a `description` dele no OpenAPI e nos tipos do frontend. Por isso os comentários das classes ficam em `#`, e as quatro docstrings que existem (`ProfilePatchRequest`, `PasswordRequest`, `PrivacyRequestUpdate` e `TranscriptMessageResponse`) já fazem parte do contrato.
- **Nome repetido.** `ConversationSummaryResponse` existe em `conversations.py` e em `insights.py`. O OpenAPI separa os dois pelo caminho do módulo: `app__schemas__conversations__ConversationSummaryResponse` e `app__schemas__insights__ConversationSummaryResponse`.

### Cada modelo e o endpoint que o usa

| Modelo | Endpoint | Papel |
|---|---|---|
| `ErrorResponse`, com `ErrorBody` | Todas as rotas de `/v1`, nos erros | Resposta de erro. `retry_after_seconds`, `message_id` e `field_errors` só saem quando têm valor |
| `LegalVersionsResponse` | `GET /v1/legal/versions` | Resposta |
| `LoginRequest` | `POST /v1/auth/login` | Pedido |
| `ProfileResponse` | `POST /v1/auth/login`, `GET /v1/me`, `PATCH /v1/me`, `POST /v1/registration/sessions/{id}/acceptance` e `POST /v1/registration/form` | Resposta |
| `AdminProbeResponse` | `GET /v1/admin/probe`, fora do OpenAPI | Resposta |
| `ProfilePatchRequest` | `PATCH /v1/me` | Pedido |
| `ConsentChangeRequest` | `PUT /v1/me/consents/{purpose}` | Pedido |
| `ConsentsResponse`, com `ConsentStateResponse` e `ConsentItemResponse` | `GET /v1/me/consents` e `PUT /v1/me/consents/{purpose}` | Resposta |
| `ExportResponse`, com `ExportProfile`, `ExportConversation`, `ExportMessage`, `ExportCitation` e `ConsentItemResponse` | `GET /v1/me/export` | Resposta, servida como arquivo |
| `AskRequest` | `POST /v1/conversations/{id}/messages` | Pedido. A resposta é `text/event-stream`, sem modelo |
| `ConversationCreatedResponse` | `POST /v1/conversations` | Resposta 201 |
| `ConversationListResponse`, com o `ConversationSummaryResponse` de `conversations.py` | `GET /v1/conversations` | Resposta |
| `ConversationResponse`, com `MessageResponse` e `CitationResponse` | `GET /v1/conversations/{id}` | Resposta |
| `FeedbackRequest` e `FeedbackResponse` | `POST /v1/messages/{id}/feedback` | Pedido e resposta 201 |
| `DocumentListResponse`, com `DocumentResponse` e `DocumentVersionResponse` | `GET /v1/admin/documents` | Resposta |
| `DocumentResponse` | `POST /v1/admin/documents` (201), `POST /v1/admin/documents/{id}/replace` e `/retry` (202) e `POST /v1/admin/documents/{id}/archive` (200) | Resposta. O pedido é multipart, declarado na rota |
| `OverviewResponse`, com `MetricResponse`, `TrendPointResponse`, `FunnelRowResponse` e `BudgetResponse` | `GET /v1/admin/overview` | Resposta |
| `QualityResponse`, com o `ConversationSummaryResponse` de `insights.py` | `GET /v1/admin/quality` | Resposta |
| `InspectionResponse`, com `InspectorMessageResponse` e `InspectorCitationResponse` | `GET /v1/admin/conversations/{id}` | Resposta |
| `RevealRequest` e `IdentityResponse` | `POST /v1/admin/conversations/{id}/reveal` | Pedido e resposta |
| `PrivacyRequestCreate` e `PrivacyRequestResponse` | `POST /v1/privacy/requests` | Pedido e resposta 201 |
| `PrivacyQueueResponse`, com `PrivacyQueueItemResponse` | `GET /v1/admin/privacy/requests` | Resposta |
| `PrivacyRequestUpdate` e `PrivacyQueueItemResponse` | `PATCH /v1/admin/privacy/requests/{id}` | Pedido e resposta |
| `RegistrationSessionResponse`, com `RegistrationFieldsResponse` e `TranscriptMessageResponse` | `POST /v1/registration/sessions` (201), `GET /v1/registration/sessions/{id}` e os `POST` e `PATCH` da sessão, menos o aceite | Resposta |
| `RegistrationMessageRequest` | `POST /v1/registration/sessions/{id}/messages` | Pedido |
| `FieldsPatchRequest` | `PATCH /v1/registration/sessions/{id}/fields` | Pedido |
| `PasswordRequest` | `POST /v1/registration/sessions/{id}/password` | Pedido |
| `ReviewRequest` | `POST /v1/registration/sessions/{id}/review` | Pedido |
| `AcceptanceRequest` | `POST /v1/registration/sessions/{id}/acceptance` | Pedido |
| `FormRequest` | `POST /v1/registration/form` | Pedido |

Rotas sem modelo nesta pasta: `GET /health` e `GET /ready` devolvem um dicionário, `GET /metrics` devolve texto do Prometheus, `GET /v1/diagnostics/stream` é um fluxo SSE, e `POST /v1/auth/logout` e `DELETE /v1/me` respondem 204 sem corpo.

## Testes

Não há teste só dos modelos. O que os cobre:

- O job `contract` da [CI](../../../../.github/workflows/ci.yml) gera o OpenAPI e os tipos de novo e falha se diferirem do que está commitado (NFR-16). Mudou um modelo, rode `uv run python -m app.scripts.export_openapi` em `apps/api` e `pnpm openapi-types` em `apps/web`.
- [`tests/unit/test_errors.py`](../../tests/unit/test_errors.py): o envelope da seção 12, com `message_id`, `retry_after_seconds` e `field_errors` só quando valem.
- [`tests/unit/test_http_guards.py`](../../tests/unit/test_http_guards.py): o 422 de validação e o 403 de origem no mesmo envelope.
- Os testes de rota em [`tests/integration`](../../tests/integration/), como [`test_conversations.py`](../../tests/integration/test_conversations.py), [`test_registration.py`](../../tests/integration/test_registration.py), [`test_account.py`](../../tests/integration/test_account.py) e [`test_admin_privacy.py`](../../tests/integration/test_admin_privacy.py), mandam corpos válidos e inválidos e leem as respostas.

## Leia também

- [SDD 12](../../../../docs/sdd/api.md#12-api-http): o contrato de cada endpoint, inclusive o envelope de erro.
- [SDD 6.6](../../../../docs/sdd/arquitetura.md#66-contrato-entre-api-e-frontend) e [8.5](../../../../docs/sdd/arquitetura.md#85-regras-dos-campos): o contrato gerado e as regras de campo do domínio.
- [A pasta dos controladores](../controllers/), que usam estes modelos.
- [Guia, parte 3: a API por dentro](../../../../docs/guia/03-api-por-dentro.md) e [parte 11: o frontend por dentro](../../../../docs/guia/11-frontend-por-dentro.md), com o cliente tipado.
