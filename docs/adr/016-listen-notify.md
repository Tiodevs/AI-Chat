# ADR-016 — PostgreSQL `LISTEN/NOTIFY` para acordar os fluxos do atendimento

Proposto em 2026-11-10, em revisão na Etapa 17.0 (seção 29.6 do SDD).

## Contexto

No atendimento humano, uma mensagem gravada por um pedido precisa chegar a fluxos SSE abertos por outros pedidos, às vezes em outro processo: durante um deploy, a versão nova e a antiga ficam no ar ao mesmo tempo, e o caminho de escala da seção 6.5 prevê mais de uma réplica. A varredura do `lifespan` também muda atendimentos sem pedido de ninguém. O banco é a fonte da verdade, e o ADR-002 mantém o PostgreSQL como único armazenamento.

## Decisão

O repositório chama `pg_notify('atrium_handoff', carga)` dentro da mesma transação que grava a mensagem ou o status. A carga é um JSON com `handoff_id`, `seq` e `kind`, sem dado pessoal além do id. Cada processo da API mantém uma conexão asyncpg fora do pool com `LISTEN atrium_handoff`, que reconecta com espera crescente, e distribui o aviso aos fluxos do próprio processo pela porta `RealtimeBroker`. O fluxo lê o conteúdo do banco, com a autorização dele, e a cada tique de 15 segundos também lê o que tem `seq` maior que o último enviado.

## Consequências

- O PostgreSQL entrega o aviso só depois do commit e nunca depois de um rollback, então nenhum fluxo mostra o que não foi gravado.
- Funciona com uma réplica, com várias e no meio de um deploy, sem serviço novo.
- Uma conexão a mais por processo, fora das 10 do pool da seção 6.4.
- Um aviso perdido enquanto o ouvinte reconecta atrasa no máximo um tique, por causa da leitura periódica do `seq`.
- A carga tem limite de 8.000 bytes no PostgreSQL. A do Atrium tem menos de 200.
- O `NOTIFY` disputa uma trava no commit quando há muita escrita. No volume do atendimento, o custo é pequeno, e a seção 6.5 o reavalia.
- Os testes usam o `InMemoryBroker`. A integração confere o adaptador do PostgreSQL com o banco da CI.

## Alternativas

- **Fila em memória do processo.** Simples, mas perde o aviso entre processos: no deploy ou com duas réplicas, o visitante de uma não recebe a mensagem gravada na outra.
- **Redis com publicação e assinatura.** Um serviço novo para operar e proteger, e mais um lugar por onde o atendimento passaria.
- **Cada fluxo consulta o banco a cada segundo.** A carga cresce com o número de telas abertas, e a latência fica presa ao intervalo.
