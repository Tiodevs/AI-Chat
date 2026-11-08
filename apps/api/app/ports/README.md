# ports

Os `Protocol` que serviços e workflows usam para falar com o mundo de fora: modelo de chat, embedding, rastro e feedback do LangSmith, relógio, hash de senha, extração de texto, orçamento de tokens e busca híbrida. É a metade "porta" do padrão portas e adaptadores, na camada de infraestrutura do [SDD 6.2](../../../../docs/sdd/arquitetura.md#62-mvc-com-as-camadas-de-que-um-sistema-de-ia-precisa); as portas dos provedores estão na [seção 17](../../../../docs/sdd/observabilidade.md#17-portas-dos-provedores).

## Arquivos

Os caminhos de "Quem usa" são relativos a `apps/api/app`.

| Arquivo | O que faz | Quem usa |
|---|---|---|
| [`__init__.py`](__init__.py) | Marca o pacote e explica o padrão | Todo `import app.ports...` |
| [`chat.py`](chat.py) | `ChatProvider`, os tipos neutros `Message`, `Tool`, `ToolResult` e `TokenUsage`, o `RunContext` de cada chamada e a soma `UsageTally` | `workflows/qa.py`, `workflows/registration.py`, `evals/evaluators.py`, `services/conversations.py`, `core/container.py` e os adaptadores de chat |
| [`embedding.py`](embedding.py) | `EmbeddingProvider` | `workflows/qa.py`, `services/retrieval.py`, `services/ingestion.py`, `core/container.py` e os adaptadores de embedding |
| [`tracing.py`](tracing.py) | `TraceRecorder` e o `NullTracer`, que descarta tudo | `workflows/qa.py`, `workflows/registration.py`, `services/ingestion.py`, `core/container.py`, `scripts/seed.py` |
| [`feedback.py`](feedback.py) | `FeedbackSink` | `services/conversations.py`, `adapters/langsmith_tracing.py` |
| [`budget.py`](budget.py) | `TokenBudget` | `services/conversations.py`, `services/question.py`, `services/registration.py` |
| [`search.py`](search.py) | `HybridSearch` | `workflows/qa.py` |
| [`clock.py`](clock.py) | `Clock` | Quase todos os serviços, os controladores que precisam da hora, `core/container.py`, `adapters/circuit_breaker.py` e `adapters/gemini_chat.py` |
| [`password_hasher.py`](password_hasher.py) | `PasswordHasher` | `services/auth.py`, `services/registration.py` |
| [`text_extractor.py`](text_extractor.py) | `TextExtractor` | `services/ingestion.py` |

## Como ler

Um `Protocol` descreve os métodos que um objeto precisa ter, sem exigir herança: qualquer classe com a mesma forma serve, e o mypy confere a forma. O caso de uso recebe a porta pelo construtor, e a raiz de composição ([`core/container.py`](../core/container.py)) escolhe o adaptador. É o padrão Strategy da seção 6.2: `APP_AI_ADAPTER` escolhe `gemini`, `fake` ou `demo`, e sem `GEMINI_API_KEY` entram os provedores indisponíveis, que falham só na chamada.

| Porta | Implementações | Quem escolhe | Onde é usada |
|---|---|---|---|
| `ChatProvider` | `GeminiChatProvider`, `FakeChatProvider`, `DemoChatProvider` e `UnavailableChatProvider`, em [`app/adapters`](../adapters/README.md) | `build_chat_provider` | `QaWorkflow` (reescrita e geração), `RegistrationWorkflow` (extração e frase), juiz de `evals/evaluators.py` |
| `EmbeddingProvider` | `GeminiEmbeddingProvider`, `DeterministicEmbeddingProvider`, `LexicalEmbeddingProvider` e `UnavailableEmbeddingProvider` | `build_embedding_provider` | `QaWorkflow`, `RetrievalService.search`, `IngestionService` |
| `TraceRecorder` | `LangSmithTracer` e, nesta pasta, `NullTracer` | `tracer_for`, ou `NullTracer` sem LangSmith | `QaWorkflow`, `RegistrationWorkflow`, `IngestionService` |
| `FeedbackSink` | `LangSmithFeedbackSink` e `NoopFeedbackSink` | `feedback_sink_for` | `send_user_feedback`, de `ConversationService` |
| `Clock` | `SystemClock` | `get_clock` | Serviços, controladores com hora, `CircuitBreaker`, `GeminiChatProvider` |
| `PasswordHasher` | `Argon2idPasswordHasher` | `get_password_hasher` | `AuthService`, `BootstrapAdminService`, `RegistrationService` |
| `TextExtractor` | `FileTextExtractor` | `core/container.py` e `scripts/seed.py` | `IngestionService` |
| `TokenBudget` | `PostgresTokenBudget`, em `services/budget.py` | `core/container.py` e `scripts/ask.py` | `ConversationService`, `QuestionService`, `RegistrationService` |
| `HybridSearch` | `RetrievalService`, em `services/retrieval.py` | `build_ai_runtime` e `scripts/run_evals.py` | `QaWorkflow` |

Ordem sugerida: [`chat.py`](chat.py), que tem a porta mais rica, depois [`embedding.py`](embedding.py), [`search.py`](search.py) e [`tracing.py`](tracing.py), que aparecem juntos no `QaWorkflow`, e por fim as portas pequenas. Pontos que ajudam:

- **O ciclo do `RunContext`.** O workflow cria um contexto por chamada ao modelo, o adaptador soma nele os tokens a cada pedaço da resposta, e o serviço lê o total pelo `UsageTally` para o orçamento, inclusive numa resposta cancelada no meio (seções 6.4 e 7.1).
- **Erros.** O chat levanta erros de domínio: `ProviderUnavailable` e `CircuitOpen`. O embedding ainda levanta `EmbeddingRequestError`, um tipo do adaptador do Gemini que o `QaWorkflow` importa; a [Etapa 13.2](../../../../docs/plano-de-acao.md#etapa-132--embedding-resiliente-atrás-da-porta) move o erro para a porta ou para o domínio.
- **Síncrono ou assíncrono.** `PasswordHasher` e `TraceRecorder` são síncronos; as outras portas são `async`. O argon2 roda hoje no loop de eventos, e a [Etapa 13.1](../../../../docs/plano-de-acao.md#etapa-131--loop-de-eventos-livre) o leva para uma thread.
- **`stream` não é `async def`.** Ele devolve um iterador assíncrono, que o workflow percorre com `async for`.

## Testes

Os testes nunca chamam o Gemini nem o LangSmith (NFR-3). Eles trocam a porta por um falso:

- [`test_qa.py`](../../tests/unit/test_qa.py): `QaWorkflow` com `FakeChatProvider`, um embedding, uma busca e um rastreador falsos escritos no teste.
- [`test_qa_provider.py`](../../tests/unit/test_qa_provider.py): `GeminiChatProvider` pela porta, com um backend falso, nova tentativa, tempo limite e circuito.
- [`test_registration_workflow.py`](../../tests/unit/test_registration_workflow.py) e [`test_demo_adapter.py`](../../tests/unit/test_demo_adapter.py): o cadastro e o adaptador `demo` pela porta de chat.
- [`test_evaluators.py`](../../tests/unit/test_evaluators.py): o juiz de fundamentação com um chat falso.
- [`test_budget.py`](../../tests/unit/test_budget.py): `TokenBudget` em memória e o `PostgresTokenBudget` sem banco.
- [`test_feedback_delivery.py`](../../tests/unit/test_feedback_delivery.py), [`test_password_hasher.py`](../../tests/unit/test_password_hasher.py), [`test_text_extractor.py`](../../tests/unit/test_text_extractor.py) e [`test_trace_policy.py`](../../tests/unit/test_trace_policy.py): os adaptadores do feedback, do hash, da extração e do rastro.
- [`test_gemini_embedding.py`](../../tests/contract/test_gemini_embedding.py): o contrato de embedding, com HTTP simulado: N textos geram N pedidos e N vetores.
- Integração: [`test_missing_gemini_key.py`](../../tests/integration/test_missing_gemini_key.py) e [`test_process_lifetime.py`](../../tests/integration/test_process_lifetime.py) sobem a API com provedores trocados; os outros testes de integração usam um relógio congelado no lugar do `SystemClock`.

## Leia também

- SDD: [6.2 Camadas e padrões](../../../../docs/sdd/arquitetura.md#62-mvc-com-as-camadas-de-que-um-sistema-de-ia-precisa), [17 Portas dos provedores](../../../../docs/sdd/observabilidade.md#17-portas-dos-provedores), [7.1 Orçamento e degradação](../../../../docs/sdd/arquitetura.md#orçamento-e-degradação) e [18.4 LangSmith](../../../../docs/sdd/observabilidade.md#184-langsmith).
- ADRs: [004, Gemini atrás de portas](../../../../docs/adr/004-gemini-atras-de-portas.md) e [014, adaptador `demo`](../../../../docs/adr/014-adaptador-demo.md).
- Guia: [3. A API por dentro](../../../../docs/guia/03-api-por-dentro.md) e [13. Testes](../../../../docs/guia/13-testes.md).
- Pastas vizinhas: [`adapters`](../adapters/README.md), [`domain`](../domain/README.md) e [`prompts`](../prompts/README.md).
