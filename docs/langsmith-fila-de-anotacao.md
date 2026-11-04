# Fila de anotação "atrium-review" no LangSmith

Seção 18.4 do SDD. A fila junta as execuções que a pessoa que opera precisa olhar: as que o visitante marcou como não úteis e as que a fundamentação recusou.

A automação é feita na interface do LangSmith. O repositório não tem como criá-la por código, então este documento é o registro do que configurar.

## Antes de começar

- Projeto `atrium-prod` (produção) com rastros chegando. Em `development`, use `atrium-dev`.
- Cada execução raiz de uma pergunta tem o id da mensagem do assistente como `run_id`.
- O feedback do visitante vira a chave `user_helpful`, com nota 1 ou 0, pela tarefa de fundo da seção 18.4.
- O desfecho `grounding_failed` fica nos metadados do rastro, na chave `outcome`.

## 1. Criar a fila

1. No LangSmith, abra **Annotation Queues** e escolha **New queue**.
2. Nome: `atrium-review`.
3. Descrição: `Respostas marcadas como não úteis e respostas recusadas pela fundamentação.`
4. Se o LangSmith pedir critérios de revisão, crie `corrigir_corpus`, `ajustar_limiar`, `ajustar_prompt` e `sem_acao`.
5. Salve.

## 2. Automação para `user_helpful = 0`

1. Abra o projeto `atrium-prod`, aba **Automations**, e escolha **Add rule**.
2. Nome: `review-nao-util`.
3. Filtro: execuções raiz com feedback `user_helpful` igual a `0`.
4. Taxa de amostragem: `1.0`.
5. Ação: **Add to annotation queue**, fila `atrium-review`.
6. Marque para aplicar também a execuções que receberem o feedback depois de criadas (feedback tardio), porque o visitante vota depois da resposta.
7. Salve.

## 3. Automação para `grounding_failed`

1. Na mesma aba, **Add rule**.
2. Nome: `review-grounding-failed`.
3. Filtro: execuções raiz com o metadado `outcome` igual a `grounding_failed`.
4. Taxa de amostragem: `1.0`.
5. Ação: **Add to annotation queue**, fila `atrium-review`.
6. Salve.

## 4. Conferir (CA-3)

1. Faça uma pergunta no Atrium em produção ou em `development`.
2. Marque a resposta como não útil.
3. Em alguns minutos, a execução aparece em **Annotation Queues**, fila `atrium-review`.
4. Para o segundo caso, faça uma pergunta que a fundamentação recuse, ou filtre o projeto por `outcome = grounding_failed` e confirme que as execuções aparecem na fila.

## Revisão semanal

Quem opera revisa a fila toda semana.

- Reescreva os casos úteis sem dado pessoal e leve-os para o conjunto de avaliação.
- Alta de `abstained` ou `grounding_failed` aponta para o corpus ou para o limiar (seção 18.5).
- Depois de revisar, tire o item da fila.
