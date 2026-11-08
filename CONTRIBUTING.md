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

Siga [Rodar localmente](README.md#rodar-localmente). O caminho mais curto é `docker compose up --build`, que sobe tudo com o adaptador de IA `fake`, sem precisar de chave. As variáveis de ambiente, os scripts e os problemas comuns estão no [guia, parte 2](docs/guia/02-rodar-e-explorar.md).

## Convenções

- **Idioma.** Texto visível ao usuário em português (`apps/web/src/i18n/pt.ts` e `apps/api/app/prompts`). Código, rotas e identificadores em inglês.
- **Camadas da API.** Respeite a direção de dependência do [SDD 6.2](docs/sdd/arquitetura.md#62-mvc-com-as-camadas-de-que-um-sistema-de-ia-precisa). O teste de arquitetura falha quando uma camada importa o que não deve.
- **Interface.** Use os componentes e tokens do design system ([SDD 14](docs/sdd/experiencia.md)) e o GSAP para movimento ([SDD 16](docs/sdd/experiencia.md)), respeitando `prefers-reduced-motion`.
- **Prompts.** Mudou o texto de um prompt, mude também a `PROMPT_VERSION`.
- **Testes sem rede.** Testes automáticos nunca chamam o Gemini nem o LangSmith. Use `FakeChatProvider`, `DeterministicEmbeddingProvider` e `NoopFeedbackSink`.
- **Segredos.** Nunca commite `.env`, chaves, senhas ou `.claude/settings.local.json`.
- **Dados.** Use só dados fictícios. O hospital, as pessoas e os telefones (prefixo 555) são inventados.

## Como documentar

A documentação tem quatro níveis. Cada um responde a uma pergunta e cita o nível de cima em vez de repetir o que ele já diz.

| Nível | Pergunta | Onde |
|---|---|---|
| Especificação | O que o sistema faz e por quê | [`docs/sdd.md`](docs/sdd.md), [`docs/sdd/`](docs/sdd/) e [ADRs](docs/adr/) |
| Guia | Como as peças trabalham juntas no código | [`docs/guia/`](docs/guia/README.md) |
| README de pasta | O que cada arquivo da pasta faz e quem o usa | `README.md` de cada pasta de código |
| Comentário | Por que esta função ou esta linha é assim | No próprio arquivo |

O [mapa da documentação](docs/README.md) lista todos os documentos e diz para que serve cada um.

### Comentários no código

- Português, frases curtas e voz ativa. Identificadores, rotas e nomes de arquivo entre crases.
- Todo arquivo começa dizendo o papel dele: docstring de módulo no Python e um bloco `/** ... */` antes dos imports no TypeScript. Diga a camada, quem usa o arquivo, o que ele usa e a seção do SDD.
- Classes, funções, hooks e componentes exportados têm docstring ou JSDoc: o que fazem, o que devolvem quando não é óbvio, os efeitos colaterais (transação, rede, cookie, log, métrica) e os erros que levantam.
- Um passo a passo longo ganha uma lista numerada na docstring, e cada passo ganha um comentário `# 1.` (ou `// 1.`) na linha onde começa.
- O comentário de linha explica o porquê: a regra do SDD, o caso de borda, a ordem que importa, o número que parece mágico, o risco que a linha evita. Não narre o que o código já diz.
- Uma regra de negócio é escrita uma vez, no SDD. O comentário cita a seção ("Seção 7.1 do SDD") em vez de copiar a regra.
- Quando o código ainda não faz o que o SDD pede e o plano tem uma etapa para isso, o comentário cita a etapa, por exemplo "A Etapa 13.1 tira isto do loop de eventos".
- Largura: até 100 colunas no Python (Ruff) e até 80 no TypeScript (Prettier).

### README de pasta

Toda pasta de código tem um `README.md` com o mesmo formato:

```markdown
# nome-da-pasta

Uma ou duas frases: o papel da pasta, a camada e a seção do SDD.

## Arquivos

| Arquivo | O que faz | Quem usa |
|---|---|---|

## Como ler

Ordem sugerida de leitura e os conceitos que ajudam (opcional).

## Testes

## Leia também
```

### Cuidados que os testes cobram

- Os textos de `apps/api/app/prompts` têm o hash travado em `tests/unit/test_prompt_versions.py`. Comente fora das strings: mudar uma letra de um prompt exige uma `PROMPT_VERSION` nova.
- As classes Pydantic de saída estruturada do modelo (`QuestionClassification`, `PhraseText` e `GroundednessJudgement`) vão para o Gemini como schema, com a docstring e as descrições dos campos. Elas fazem parte do prompt, mesmo fora de `app/prompts`: explique com comentários `#`, e uma mudança nelas pede uma `PROMPT_VERSION` nova.
- Em `apps/web/src`, o teste de cores cruas também lê os comentários. Não escreva `#` num comentário, nem classes de paleta do Tailwind (como `bg-neutral-900`), nem `rgb(`, `hsl(` ou `oklch(`, fora de `styles/tokens.css`.
- O FastAPI usa a docstring de cada rota como `description` no OpenAPI, e o Pydantic faz o mesmo com a docstring de cada schema. O job `contract` da CI compara o `openapi.json` gerado com o commitado. Para explicar mais numa rota sem mudar o contrato, ponha a explicação depois de uma linha com `\f`, onde o FastAPI corta a descrição; num schema, use comentários `#`. Se a descrição pública mudar de propósito, gere de novo o OpenAPI e os tipos (seção "Antes de abrir a PR").
- `apps/api/app/workflows/qa.py` não pode conter os nomes `GEMINI_API_KEY` e `LANGSMITH_API_KEY`, nem num comentário.
- `.github/workflows/ci.yml` não pode conter a palavra `langsmith`, em nenhuma caixa.
- `content/corpus/README.md` só pode citar telefones e faixas de horário do catálogo da seção 9.
- `apps/api/.env.example` lista exatamente os campos de `Settings`. Comentários começam com `#`.

### Quando atualizar

- Mudou o comportamento: SDD, comentários e README da pasta na mesma PR.
- Mudou um fluxo entre camadas, como a ordem das chamadas ou um arquivo novo no caminho: também a página do guia.
- Criou ou removeu um arquivo: a tabela do README da pasta.

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
