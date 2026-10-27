# Provedores e observabilidade

Parte da [especificação do Atrium](../sdd.md). A numeração das seções é a do documento completo.

## 17. Portas dos provedores

```python
class ChatProvider(Protocol):
    model_name: str

    async def complete_structured(self, messages: list[Message], schema: type[Model], run: RunContext) -> Model: ...

    async def complete_with_tools(self, messages: list[Message], tools: list[Tool], run: RunContext) -> ToolResult: ...

    def stream(self, messages: list[Message], run: RunContext) -> AsyncIterator[str]: ...


class EmbeddingProvider(Protocol):
    model_name: str
    dimensions: int

    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...


class FeedbackSink(Protocol):
    async def record(self, run_id: UUID, key: str, score: float) -> None: ...
```

`RunContext` carrega `run_id`, `request_id`, `prompt_version`, `trace_policy` (`full`, `masked` ou `metadata_only`) e as tags. Os adaptadores traduzem isso para a configuração de execução do LangChain.

| Adaptador | Quando é usado |
|---|---|
| `GeminiChatProvider` | Envolve o `ChatGoogleGenerativeAI` do LangChain com `CHAT_MODEL`, tempo limite, nova tentativa e circuit breaker. |
| `GeminiEmbeddingProvider` | Chama `embedContent` de `EMBEDDING_MODEL` com `outputDimensionality` igual a `EMBEDDING_DIMENSIONS`. Um texto por pedido HTTP, no máximo 4 simultâneos, com nova tentativa em 429. |
| `LangSmithFeedbackSink` | Envia o feedback do visitante ao LangSmith. |
| `FakeChatProvider` | Testes. Valores estruturados, chamadas de ferramenta e fluxos de token escritos no teste. |
| `DeterministicEmbeddingProvider` | Testes. Vetor unitário de 768 dimensões gerado por hash. O mesmo texto devolve sempre o mesmo vetor. |
| `NoopFeedbackSink` | Testes e ambiente sem LangSmith. |

**Contrato de embedding.** O `gemini-embedding-2` agrega várias entradas enviadas juntas num único embedding. Por isso o `GeminiEmbeddingProvider.embed_documents` envia um texto por pedido, com no máximo 4 pedidos simultâneos e nova tentativa em 429. Um teste de contrato, com HTTP simulado, confere que N textos geram N pedidos e N vetores de 768 dimensões.

`APP_AI_ADAPTER=gemini` é o padrão. `APP_AI_ADAPTER=fake` serve para trabalhar a interface localmente sem chave. Os testes de integração injetam os falsos explicitamente, para uma variável esquecida não chamar o Gemini.

A configuração é lida uma vez com Pydantic Settings:

`APP_ENV` (`local`, `test`, `development`, `production`), `DATABASE_URL`, `GEMINI_API_KEY`, `CHAT_MODEL`, `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS`, `APP_AI_ADAPTER`, `WEB_ORIGIN`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `RETRIEVAL_MIN_SIMILARITY`, `LLM_DAILY_TOKEN_BUDGET`, `METRICS_TOKEN`, `RATE_LIMIT_HMAC_KEY`, `PSEUDONYM_KEY`, `PRIVACY_CONTACT_EMAIL`, `LOG_LEVEL`, `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`, `LANGSMITH_ENDPOINT`, `LANGSMITH_TRACING_SAMPLING_RATE`.

A `DATABASE_URL` da Railway usa o esquema `postgresql://`. A configuração a reescreve para `postgresql+asyncpg://`. A API usa sessões assíncronas do SQLAlchemy 2 e asyncpg.

## 18. Observabilidade

Quatro sinais, cada um com um trabalho:

| Sinal | Pergunta que responde | Ferramenta |
|---|---|---|
| Logs | O que aconteceu neste pedido? | `structlog` em JSON, lido na Railway |
| Rastros de sistema | Onde o tempo foi gasto, entre HTTP, banco e provedores? | OpenTelemetry, recebido pela Railway |
| Métricas | Como o sistema está se comportando ao longo do tempo? | Prometheus e Grafana |
| Rastros de IA | O que o modelo recebeu, recuperou e respondeu, e com que qualidade? | LangSmith |

O `request_id` liga os quatro. Ele está no log, como atributo do span, como metadado do rastro do LangSmith e na resposta HTTP.

### 18.1 Logs

O `structlog` escreve um objeto JSON por evento na stdout. Campos obrigatórios: `timestamp`, `level`, `event`, `request_id`, `trace_id`, `span_id`, `route`, `status_code`, `duration_ms`, `app_version`. O id do usuário entra como pseudônimo quando existe uma sessão.

Um processador descarta campos cujo nome está na lista de recusa (`password`, `email`, `phone`, `text`, `content`, `body`, `authorization`, `cookie`, `ip`) e aplica regex de e-mail e telefone aos valores restantes, antes da linha ser emitida.

### 18.2 Rastros de sistema

O processo começa com `opentelemetry-instrument`, para o SDK carregar antes de FastAPI, SQLAlchemy, asyncpg e httpx. Os pacotes de instrumentação vêm de `opentelemetry-bootstrap -a install` e ficam no `pyproject.toml`.

O SDK lê `OTEL_EXPORTER_OTLP_*` do ambiente. O código não fixa um endpoint. Na Railway, o tracing fica ligado no ambiente `production`, com `OTEL_METRICS_EXPORTER=none` e `OTEL_LOGS_EXPORTER=none`, porque o receptor aceita só rastros. Localmente, `OTEL_TRACES_EXPORTER=console` é opcional.

Spans próprios, filhos do span do pedido:

| Span | Atributos |
|---|---|
| `qa.rewrite` | `intent`, `model`, `prompt_version` |
| `qa.embed_query` | `model`, `dimensions` |
| `qa.retrieve` | `candidate_count`, `top_similarity` |
| `qa.generate` | `model`, `input_tokens`, `output_tokens`, `prompt_version` |
| `qa.ground` | `outcome` |
| `registration.extract` | `field_names`, `model` |
| `registration.decide` | `next_step` |
| `ingestion.extract` | `media_type`, `byte_size` |
| `ingestion.embed` | `chunk_count`, `model` |
| `ingestion.publish` | `document_id`, `version` |
| `retention.run` | `rule`, `deleted_count` |

Os atributos usam ids, contagens, enums e durações, nunca texto de pergunta ou de documento. Um span com falha registra o tipo da exceção e marca erro. Cada span de IA guarda `langsmith.run_id` como atributo, e cada rastro do LangSmith guarda o `trace_id`, para navegar entre os dois.

### 18.3 Métricas, painéis e alertas

A API expõe Prometheus em `GET /metrics`, protegida por `METRICS_TOKEN`. No ambiente `production` da Railway, um serviço Prometheus coleta `http://api.railway.internal:$PORT/metrics` pela rede privada a cada 30 segundos, e um serviço Grafana lê o Prometheus. A API escuta em `::` para aceitar conexões da rede privada.

| Métrica | Tipo | Rótulos |
|---|---|---|
| `atrium_http_requests` | counter | `route`, `method`, `status` |
| `atrium_http_request_duration_seconds` | histogram | `route` |
| `atrium_qa_outcomes` | counter | `outcome` |
| `atrium_qa_first_token_seconds` | histogram | nenhum |
| `atrium_qa_top_similarity` | histogram | nenhum |
| `atrium_llm_tokens` | counter | `model`, `direction` |
| `atrium_llm_duration_seconds` | histogram | `operation` |
| `atrium_llm_budget_ratio` | gauge | nenhum |
| `atrium_llm_circuit_open` | gauge | nenhum |
| `atrium_registration_events` | counter | `event`, `path` |
| `atrium_ingestion_versions` | counter | `status` |
| `atrium_feedback` | counter | `rating` |
| `atrium_dsr_open` | gauge | `overdue` |
| `atrium_retention_deleted` | counter | `rule` |

`route` é o modelo do caminho, nunca o id cru. Eventos de cadastro: `started`, `extracted`, `optional_skipped`, `password_set`, `completed`, `abandoned`.

Painéis no Grafana, versionados como JSON em `ops/grafana/`:

| Painel | Conteúdo |
|---|---|
| Atrium, saúde da API | Taxa de pedidos, erros 5xx, latência por rota e prontidão |
| Atrium, qualidade de IA | Desfechos, similaridade, primeiro token, tokens por dia, orçamento e circuito |
| Atrium, cadastro | Funil por etapa e por caminho, abandono |
| Atrium, privacidade | Pedidos abertos e atrasados, eliminações por regra |

Alertas, com contato por e-mail para quem opera:

| Alerta | Condição |
|---|---|
| Erros da API | 5xx acima de 2% por 10 minutos |
| Latência de IA | p95 do primeiro token acima de 3 s por 30 minutos |
| Qualidade em queda | `abstained` mais `grounding_failed` acima de 25% das respostas em 1 hora |
| Orçamento | `atrium_llm_budget_ratio` acima de 0,8 |
| Circuito aberto | `atrium_llm_circuit_open` igual a 1 por 5 minutos |
| Ingestão | Qualquer versão `failed` na última hora |
| Pedido de titular atrasado | `atrium_dsr_open{overdue="true"}` acima de 0 |
| Retenção parada | Nenhuma execução de `retention-job` em 26 horas |

A página de qualidade do admin usa agregados do banco, não o Prometheus, para funcionar mesmo sem o Grafana.

### 18.4 LangSmith

**Papel.** O LangSmith mostra o que o OpenTelemetry não mostra: prompts, documentos recuperados, saída do modelo, tokens, custo, feedback e avaliações.

**Configuração.**

| Variável | Local | CI | Development | Produção |
|---|---|---|---|---|
| `LANGSMITH_TRACING` | `false`, opcional `true` | `false` | `true` | `true` |
| `LANGSMITH_PROJECT` | `atrium-dev` | sem uso | `atrium-dev` | `atrium-prod` |
| `LANGSMITH_TRACING_SAMPLING_RATE` | `1.0` | sem uso | `1.0` | `1.0` na versão 1 |
| `LANGSMITH_ENDPOINT` | Estados Unidos | sem uso | Estados Unidos | Estados Unidos |

A região é a dos Estados Unidos, decisão D-2. `LANGSMITH_ENDPOINT` usa o endpoint padrão dessa região.

A raiz de composição cria o cliente do LangSmith com um `anonymizer` que troca e-mails, telefones e sequências longas de dígitos por marcadores. O `LANGSMITH_HIDE_INPUTS` global não é usado, porque ele desliga o anonimizador.

**Política de rastro por passo.**

| Passo | Política | O que vai ao LangSmith |
|---|---|---|
| `qa.rewrite` | `metadata_only` | `intent`, `confidence`, versão do prompt e tokens. Sem pergunta e sem histórico. |
| Fluxo de pergunta com `public_info` | `masked` | Pergunta autônoma reescrita, chunks recuperados, resposta, citações e desfecho, depois do anonimizador |
| Fluxo com `medical_advice` ou `other` | `metadata_only` | Só o desfecho |
| Cadastro, todos os nós | `metadata_only` | Nomes dos campos aceitos, `next_step` e tokens. Nunca valores. |
| Ingestão | `full` | Corpus público e fictício |

As políticas são aplicadas com `tracing_context` e clientes com `hide_inputs` e `hide_outputs` próprios. Um teste de unidade passa um nome, um e-mail e um telefone por cada política e confere o que sairia.

**Metadados e tags.** Cada rastro leva `request_id`, `trace_id`, `app_version`, `prompt_version`, `outcome`, `environment`, `conversation_id` e `subject`, o pseudônimo HMAC do usuário ou da chave de convidado. Tags: `qa`, `registration` ou `ingestion`.

**Ligação com o produto.** O `run_id` da execução raiz de uma pergunta é o id da mensagem do assistente. Um feedback do visitante vira, por uma tarefa de fundo, `user_helpful` com nota 1 ou 0 no LangSmith. Uma falha no envio é registrada no log e não afeta o visitante.

**Fila de anotação.** Uma automação do LangSmith manda para a fila "atrium-review" toda execução com `user_helpful = 0` e toda execução com desfecho `grounding_failed`. A pessoa que opera revisa a fila toda semana e transforma os casos úteis em exemplos de avaliação, reescritos sem dado pessoal.

**Encerramento.** O `lifespan` do FastAPI chama `wait_for_all_tracers()` no desligamento, para não perder rastros num deploy.

### 18.5 O que um operador olha

Depois de uma resposta ruim:

1. O `request_id`, na tela de erro ou no inspetor de qualidade.
2. O rastro no LangSmith, pelo link do inspetor: o que foi recuperado, o que o modelo respondeu e por que a fundamentação aceitou ou recusou.
3. O rastro do OpenTelemetry, pelo `trace_id`, se a dúvida for latência.
4. Os logs, pelo `request_id`, se a dúvida for erro.

Uma alta de `abstained` ou `grounding_failed` aponta para o corpus ou para o limiar. Uma alta de `refused` mostra pessoas fazendo perguntas clínicas que o produto deve recusar. Uma queda de útil depois de um deploy aponta para a versão do prompt, comparável no LangSmith.

