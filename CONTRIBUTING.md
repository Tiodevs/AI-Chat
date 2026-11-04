# Como contribuir com o Atrium

Obrigado pelo interesse. Este guia explica como propor uma mudança e o que uma PR precisa ter para ser aceita.

## Por onde começar

- **Encontrou um problema?** Abra uma issue com o modelo de bug: o que você fez, o que esperava e o que aconteceu.
- **Tem uma ideia?** Abra uma issue com o modelo de proposta antes de escrever o código. Assim a conversa sobre o desenho acontece antes do trabalho.
- **Quer ajudar sem uma ideia própria?** Boas portas de entrada são testes, acessibilidade, documentação e novos casos em [`evals/`](evals/README.md).

## A especificação vem antes do código

O comportamento do Atrium está descrito em [`docs/sdd.md`](docs/sdd.md), com as seções em [`docs/sdd/`](docs/sdd/). Uma PR:

- cita a seção do SDD que implementa;
- atualiza o SDD na mesma mudança quando o comportamento muda;
- registra um ADR em [`docs/adr/`](docs/adr/) quando toma uma decisão estrutural nova.

## Ambiente

Siga [Rodar localmente](README.md#rodar-localmente). O caminho mais curto é `docker compose up --build`, que sobe tudo com o adaptador de IA `fake`, sem precisar de chave.

## Convenções

- **Idioma.** Texto visível ao usuário em português (`apps/web/src/i18n/pt.ts` e `apps/api/app/prompts`). Código, rotas e identificadores em inglês.
- **Camadas da API.** Respeite a direção de dependência do [SDD 6.2](docs/sdd/arquitetura.md#62-mvc-com-as-camadas-de-que-um-sistema-de-ia-precisa). O teste de arquitetura falha quando uma camada importa o que não deve.
- **Interface.** Use os componentes e tokens do design system ([SDD 14](docs/sdd/experiencia.md)) e o GSAP para movimento ([SDD 16](docs/sdd/experiencia.md)), respeitando `prefers-reduced-motion`.
- **Prompts.** Mudou o texto de um prompt, mude também a `PROMPT_VERSION`.
- **Testes sem rede.** Testes automáticos nunca chamam o Gemini nem o LangSmith. Use `FakeChatProvider`, `DeterministicEmbeddingProvider` e `NoopFeedbackSink`.
- **Segredos.** Nunca commite `.env`, chaves, senhas ou `.claude/settings.local.json`.
- **Dados.** Use só dados fictícios. O hospital, as pessoas e os telefones (prefixo 555) são inventados.

## Branches e commits

- Branch a partir da `main`, com o nome `tipo/assunto-curto`, por exemplo `fix/citacao-duplicada`.
- Um commit por intenção, no formato `tipo: descrição curta em português`.
- Tipos: `feat`, `fix`, `docs`, `test`, `build`, `perf`, `style`, `refactor`. Não misture tipos no mesmo commit.

## Antes de abrir a PR

Rode as verificações da parte que você mexeu. A CI roda todas.

```bash
# apps/api
uv run ruff check && uv run mypy && uv run pytest
```

```bash
# apps/web
pnpm exec eslint . && pnpm test
pnpm exec tsc --noEmit -p tsconfig.app.json && pnpm exec tsc --noEmit -p tsconfig.node.json
pnpm build && pnpm build-storybook
pnpm exec playwright test
```

Se a mudança altera a API, gere de novo o OpenAPI com `uv run python -m app.scripts.export_openapi` (em `apps/api`) e os tipos com `pnpm openapi-types` (em `apps/web`). A CI confere esse contrato.

## A PR

- Descreva o que mudou e por quê, e cite a seção do SDD.
- Inclua capturas de tela quando a interface mudar.
- Diga como você testou.
- Mantenha a PR focada em um assunto. Duas mudanças independentes viram duas PRs.

## Segurança

Se encontrar uma falha de segurança ou um problema de privacidade, não abra uma issue pública. Fale com as pessoas mantenedoras de forma privada, pela aba **Security** do repositório quando o relatório privado estiver disponível.

## Convivência

Seja respeitoso e construtivo. Critique o código, não a pessoa. Comentários ofensivos, assédio ou discriminação não são aceitos, e as pessoas mantenedoras podem remover contribuições e participantes que desrespeitem isso.
