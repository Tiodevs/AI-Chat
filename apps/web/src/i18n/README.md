# i18n

Todos os textos que a pessoa vê na interface, em português do Brasil, num objeto só. Código, rotas e identificadores ficam em inglês; o texto visível fica aqui. Seção 15.7 do SDD.

## Arquivos

| Arquivo | O que faz | Quem usa |
|---|---|---|
| [pt.ts](pt.ts) | O objeto `pt`, `as const`, com os textos agrupados por tela ou componente. Um comentário antes de cada grupo diz onde ele aparece | As telas e os hooks de `features`, os componentes de `components`, a casca e as rotas de `app`, os testes de tela e a e2e |

## Como ler

Abra [pt.ts](pt.ts) e siga os comentários de grupo. Os grupos, na ordem do arquivo:

| Grupo | Onde aparece |
|---|---|
| Textos soltos (`appName`, `loading`, `couldNotContinue`...) | Título da aba, casca, diálogos, carregamento e erro genérico dos hooks |
| `pages` | O `h1` e o título da aba de cada página |
| `nav`, `sidebar`, `notice`, `profile` | Barra lateral, menu do visitante, busca ⌘K e `ProfileButton` |
| `signIn`, `forbidden`, `requestId`, `error` | Entrar, página 403 e telas de erro |
| `home`, `safety`, `ask` | Início e conversa, com as sugestões e os desfechos |
| `registration` | Cadastro por conversa e por formulário |
| `account`, `legalAccept` | Conta do membro e novo aceite |
| `privacyNotice`, `privacyRequest`, `termsOfUse` | Aviso de Privacidade, canal do titular e Termos de Uso |
| `insights`, `quality`, `documents`, `dueDate`, `privacyQueue` | As telas do admin |

Conceitos que ajudam:

- **Um objeto tipado.** `pt.ask.send` é conferido pelo `tsc`: uma chave errada não compila. O `as const` deixa os textos somente leitura e com o tipo literal.
- **Modelos com marca.** Textos como `"Tente de novo em {minutes} minutos."` têm uma marca entre chaves que o código troca com `replace`, como faz `limitMessage` em `features/auth/return-to.ts`.
- **Os testes acham a tela pelo texto.** Os testes de tela e a e2e importam `pt` e procuram os elementos pelo mesmo texto, como `getByRole("button", { name: pt.ask.send })`. Como leem o mesmo objeto, mudar um texto aqui não pede mudar o seletor.
- **O que não mora aqui.** As respostas fixas da IA e as falas do cadastro vêm da API, de `apps/api/app/prompts`, com o texto travado pelo hash e pela `PROMPT_VERSION`.

Para escrever um texto novo, siga a seção 15.7: frases curtas, sempre um próximo passo, sem culpar a pessoa, e números e horários no formato do catálogo da seção 9. `pageNotFound` ainda não tem tela; a Etapa 14.1 cria a página não encontrada.

## Testes

Não há teste do arquivo em si. O `tsc` confere cada uso, e os testes de tela e a e2e usam os textos como seletores ([README de src/test](../test/README.md) e [README de e2e](../../e2e/README.md)).

## Leia também

- [SDD 15.7, diretrizes de texto](../../../../docs/sdd/experiencia.md#157-diretrizes-de-texto)
- [SDD 15.5, telas](../../../../docs/sdd/experiencia.md#155-telas), com a cópia de cada estado
- [SDD 9, catálogo do corpus](../../../../docs/sdd/corpus.md#9-catálogo-do-corpus), para telefones e horários
- [Guia, parte 11: frontend por dentro](../../../../docs/guia/11-frontend-por-dentro.md)
