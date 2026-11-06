# ADR-014 — Adaptador `demo` por regras para a e2e com a API real

## Contexto

A seção 21.1 pede que a CI suba a API com o adaptador falso e rode as jornadas com o Playwright. O `FakeChatProvider` só responde ao que cada teste escreve; sem roteiro, toda pergunta vira indisponibilidade. O `DeterministicEmbeddingProvider` gera vetores por hash do texto, sem relação entre pergunta e chunk, então a busca nunca passa do piso de similaridade. Com eles, a e2e não provaria a J1 nem a J2.

## Decisão

`APP_AI_ADAPTER=demo` liga um chat por regras (`DemoChatProvider`) e um embedding lexical (`LexicalEmbeddingProvider`). Palavras de sintoma viram orientação médica, a resposta é a primeira frase do melhor bloco com a citação dele, e o cadastro lê o campo pelo passo atual. A configuração recusa `demo` com `APP_ENV` `development` ou `production`.

## Consequências

- O job `e2e` percorre J1, J2, J3, J4, J5 e J8 contra a API, o banco e o proxy de verdade, sem chave, sem custo e sem variação.
- As saídas do `demo` passam pelas mesmas guardas que as do Gemini: lista de permissão do cadastro, conferência de citação e de telefone.
- O `demo` não mede a qualidade da IA. Isso continua no LangSmith (seção 21.2).
- O mesmo modo serve para apresentar o produto localmente sem chave.

## Alternativas

- E2e só com respostas simuladas por `page.route`: não pega contrato, proxy, cookie, `Origin` nem CSP.
- Gemini de verdade na CI: custo, chave na CI e resultados que variam a cada execução.
