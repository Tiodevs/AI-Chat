# prompts

Os textos do Atrium em português: as respostas fixas, as mensagens de erro, as falas do cadastro e os prompts enviados ao modelo, com versão. É a camada de prompts do [SDD 6.2](../../../../docs/sdd/arquitetura.md#62-mvc-com-as-camadas-de-que-um-sistema-de-ia-precisa); as regras dos prompts estão nas seções [10.1](../../../../docs/sdd/seguranca.md#101-respostas-fixas) e [10.2](../../../../docs/sdd/seguranca.md#102-limites-do-modelo).

## Arquivos

Os caminhos de "Quem usa" são relativos a `apps/api/app`.

| Arquivo | O que faz | Quem usa |
|---|---|---|
| [`__init__.py`](__init__.py) | Marca o pacote e resume a regra das versões | Todo `import app.prompts...` |
| [`qa.py`](qa.py) | Prompts versionados da reescrita e da geração, o bloco de contexto não confiável e as quatro respostas fixas da seção 10.1, que aparecem no balão do assistente | `workflows/qa.py`, os adaptadores de chat, `scripts/ask.py`, `scripts/run_evals.py` |
| [`registration.py`](registration.py) | Prompts versionados da extração e da frase, a saudação, as perguntas modelo, a fala da revisão e as mensagens de campo do chat, do cartão de resumo, do formulário e da conta | `workflows/registration.py`, `services/registration.py`, `services/account.py` |
| [`evals.py`](evals.py) | Prompt versionado do juiz de fundamentação das avaliações. O visitante nunca vê | `evals/evaluators.py` |
| [`account.py`](account.py) | Erros da página `/account` e o nome do arquivo da exportação | `services/account.py`, `controllers/account.py` |
| [`auth.py`](auth.py) | Erros de entrar, de sessão, de `Origin` e do segredo da borda, e as mensagens do script `bootstrap_admin` | `services/auth.py`, `core/middleware.py`, `core/errors.py`, `services/conversations.py`, os scripts |
| [`conversations.py`](conversations.py) | Erros da conversa, do feedback e do fluxo de diagnóstico, e o evento `error` do SSE | `services/conversations.py`, `services/insights.py` |
| [`corpus.py`](corpus.py) | Erros de ingestão, que a lista de documentos do admin mostra, e as mensagens dos scripts de semente e de busca | `services/ingestion.py`, `services/seed.py`, `scripts/seed.py`, `scripts/search.py` |
| [`documents.py`](documents.py) | Erros de `/admin/documents` e o texto de cada `UploadIssue` | `services/documents.py` |
| [`insights.py`](insights.py) | Erros de `/admin` e `/admin/quality` | `services/insights.py` |
| [`privacy.py`](privacy.py) | Erros do canal de `/privacy` e da fila de `/admin/privacy`, e a linha final do script de retenção | `services/privacy.py`, `scripts/retention.py` |
| [`handoff.py`](handoff.py) | As mensagens dos erros do atendimento humano, o prefixo do rótulo e as do script `attendants` | `services/handoff.py`, `services/attendance.py`, `services/attendant_roles.py`, `controllers/attendance.py` e `controllers/event_stream.py` |

## Como ler

Os textos de erro e de interface são constantes simples: o serviço os põe na `message` ou nos `field_errors` do envelope da seção 12, e a tela mostra. Os prompts do modelo têm versão. Comece por [`qa.py`](qa.py) e depois [`registration.py`](registration.py):

| Versão | Texto no hash | Saída | Temperatura | Quem chama |
|---|---|---|---|---|
| `qa-rewrite@2026-10-27.1` | `REWRITE_INSTRUCTIONS`, `VISITOR_TYPE_TEMPLATE` e as descrições dos campos | `QuestionClassification`: `standalone_question`, `intent` e `confidence` | 0 | `QaWorkflow`, passo 1 da seção 7.1 |
| `qa-generate@2026-11-04.1` | `GENERATE_INSTRUCTIONS`, `UNTRUSTED_INTRO` e `UNTRUSTED_BLOCK` | Texto em fluxo, com citações `[n]` | 0,2 | `QaWorkflow`, passo 6 |
| `registration-extract@2026-10-28.2` | `EXTRACT_INSTRUCTIONS`, `SET_FIELDS_DESCRIPTION` e `TOOL_PROPERTY_DESCRIPTIONS` | Chamada da ferramenta `set_fields` | 0 | Nó `extract` do `RegistrationWorkflow` |
| `registration-phrase@2026-11-04.2` | `PHRASE_INSTRUCTIONS`, `PHRASE_TEXT_DESCRIPTION`, `GREETING`, `CORRECTION_PROMPT` e `STEP_PROMPTS` | `PhraseText`: `text` | 0,2 | Nó `phrase` do `RegistrationWorkflow` |
| `groundedness@2026-10-27.1` | `GROUNDEDNESS_INSTRUCTIONS` e `SCORE_DESCRIPTION` | `GroundednessJudgement`: `score` de 0 a 1 | 0 | `build_groundedness`, nas avaliações |

A mensagem da geração, montada em `workflows/qa.py`:

```text
system     GENERATE_INSTRUCTIONS
user       ┐ a janela do histórico, até 6 trocas e 6.000 caracteres
assistant  ┘ (domain/history.py)
user       a pergunta original do visitante
           UNTRUSTED_INTRO
           <contexto_nao_confiavel indice="1" secao="título da seção">
           conteúdo do chunk
           </contexto_nao_confiavel>
           ... até 6 blocos
```

As defesas contra injeção de prompt são em camadas, e só a primeira depende do modelo obedecer:

1. Toda instrução de sistema manda ignorar instruções vindas da mensagem do visitante ou de um documento.
2. O contexto vai delimitado e rotulado como não confiável. O conteúdo entra sem tratamento, e a [Etapa 15.3](../../../../docs/plano-de-acao.md#etapa-153--prompt-e-rastros-mais-seguros) neutraliza a tag de fechamento.
3. A ferramenta do cadastro só tem os campos da lista de permissão, e `domain/fields.py` rejeita a saída inteira com qualquer chave a mais, como `role`.
4. Código decide o que importa: `domain/outcomes.py` decide o portão, `domain/grounding.py` confere citações e telefones, e `domain/registration.py` decide o passo.
5. Onde o modelo não deve escrever, a fala é fixa: as respostas da seção 10.1, a revisão do cadastro e a resposta a um erro de campo.

Para mudar um prompt:

1. Mude o texto.
2. Mude a `*_PROMPT_VERSION` dele, com a data do dia e um contador.
3. Rode `tests/unit/test_prompt_versions.py`. Ele falha e mostra o hash novo: troque, em `_LOCKED_HASHES`, a versão antiga pela nova, com esse hash.
4. A PR que muda `app/prompts` roda o `evals.yml`, que compara a versão nova com a linha de base de `main` (seção 21.2).

Ficam fora do hash, e por isso exigem atenção na revisão: os rótulos que os workflows montam (`Passo atual:`, `passo:`, `pergunta modelo:`, `mensagem:` e o `Trechos:` do juiz), o `NO_SECTION` que vai no atributo `secao` e a mensagem que o juiz recebe. Dois textos de interface têm dependência fora daqui: o frontend procura `já tem uma conta` em `EMAIL_TAKEN` para mostrar o botão Entrar, e a fala da revisão cita os botões Está certo e Quero corrigir, de `apps/web/src/i18n/pt.ts`.

## Testes

- [`test_prompt_versions.py`](../../tests/unit/test_prompt_versions.py): trava o hash de cada versão e confere as quatro respostas fixas palavra por palavra contra a seção 10.1.
- [`test_qa.py`](../../tests/unit/test_qa.py) e [`test_budget.py`](../../tests/unit/test_budget.py): mensagens montadas e texto de cada desfecho da pergunta.
- [`test_registration_workflow.py`](../../tests/unit/test_registration_workflow.py): falas fixas, revisão e resposta a erro de campo do cadastro.
- [`test_demo_adapter.py`](../../tests/unit/test_demo_adapter.py), [`test_auth_rules.py`](../../tests/unit/test_auth_rules.py), [`test_http_guards.py`](../../tests/unit/test_http_guards.py), [`test_embedding_text.py`](../../tests/unit/test_embedding_text.py) e [`test_seed_script.py`](../../tests/unit/test_seed_script.py): usam os textos como valor esperado.
- Integração: [`test_conversations.py`](../../tests/integration/test_conversations.py), [`test_registration.py`](../../tests/integration/test_registration.py), [`test_missing_gemini_key.py`](../../tests/integration/test_missing_gemini_key.py), [`test_auth.py`](../../tests/integration/test_auth.py), [`test_bootstrap_admin.py`](../../tests/integration/test_bootstrap_admin.py), [`test_admin_documents.py`](../../tests/integration/test_admin_documents.py), [`test_admin_insights.py`](../../tests/integration/test_admin_insights.py), [`test_admin_privacy.py`](../../tests/integration/test_admin_privacy.py), [`test_privacy_requests.py`](../../tests/integration/test_privacy_requests.py) e [`test_seed.py`](../../tests/integration/test_seed.py).

## Leia também

- SDD: [7.1 Pergunta](../../../../docs/sdd/arquitetura.md#71-fazer-uma-pergunta), [7.2 Cadastro](../../../../docs/sdd/arquitetura.md#72-cadastro), [10.1 Respostas fixas](../../../../docs/sdd/seguranca.md#101-respostas-fixas), [10.2 Limites do modelo](../../../../docs/sdd/seguranca.md#102-limites-do-modelo), [15.7 Diretrizes de texto](../../../../docs/sdd/experiencia.md#157-diretrizes-de-texto) e [21.2 Avaliações](../../../../docs/sdd/entrega.md#212-avaliações-no-langsmith).
- ADR: [007, prompts versionados](../../../../docs/adr/007-prompts-versionados.md).
- Regra: [`.claude/rules/camadas.md`](../../../../.claude/rules/camadas.md).
- Guia: [4. Uma pergunta de ponta a ponta](../../../../docs/guia/04-pergunta-de-ponta-a-ponta.md), [6. Cadastro com IA](../../../../docs/guia/06-cadastro-com-ia.md) e [7. Contas, sessões e segurança](../../../../docs/guia/07-contas-sessoes-e-seguranca.md).
- Pastas vizinhas: [`domain`](../domain/README.md) e [`ports`](../ports/README.md).
