# ADR-017 — WhatsApp pela Cloud API, com caixa de entrada e caixa de saída no PostgreSQL

Proposto em 2026-11-12, em revisão na Etapa 18.0 (seção 30.2 do SDD).

## Contexto

O canal WhatsApp recebe as mensagens por um webhook da Meta. A Meta exige HTTP 200 e, sem ele, tenta de novo com frequência decrescente por até 7 dias, o que pode duplicar notificações. A pergunta à IA leva até 12 segundos no p95 (seção 5.3), e o envio da resposta depende da Graph API, que pode responder 429 ou 5xx. A versão 1 tem uma réplica da API (ADR-012), o PostgreSQL é o único armazenamento (ADR-002) e o `LISTEN/NOTIFY` já acorda o atendimento humano (ADR-016).

## Decisão

- A rota `POST /v1/whatsapp/webhook` confere a assinatura `X-Hub-Signature-256` sobre o corpo cru, grava cada evento em `whatsapp_inbound_events` com o `wamid` único, faz `pg_notify('atrium_whatsapp', ...)` na mesma transação e responde 200. Nenhum trabalho de negócio acontece antes da resposta.
- Um processador no `lifespan` acorda pelo `LISTEN` ou a cada 5 segundos, pega eventos com `FOR UPDATE SKIP LOCKED`, trava o contato com advisory lock e chama o pipeline da seção 7.1 ou o atendimento da seção 29.
- Toda mensagem a enviar é uma linha em `whatsapp_outbound_messages`, gravada na mesma transação que grava a resposta ou a mudança de status. O enviador tenta de novo com espera crescente. Os webhooks de status atualizam a linha pelo `wamid`.
- A Graph API fica atrás da porta `MessagingChannel`, com o adaptador `MetaCloudApiChannel` e o `FakeMessagingChannel` dos testes.

## Consequências

- Uma notificação repetida pela Meta não gera segunda resposta.
- Uma falha da Graph API ou um reinício não perde a resposta: a linha continua `pending`.
- Nenhum serviço novo. Funciona com uma réplica e com várias.
- O envio é pelo menos uma vez: um processo que cai entre o aceite da Meta e o commit pode enviar de novo.
- A latência da resposta soma o tempo até o processador acordar, perto de zero com o `LISTEN` e no máximo 5 segundos sem ele.
- O texto fica no banco só enquanto o evento é processado e a mensagem é entregue.

## Alternativas

- **Responder ao webhook depois de gerar a resposta.** A Meta repetiria a notificação, e o Atrium responderia duas vezes.
- **Tarefa de fundo do FastAPI sem gravar antes.** Um reinício perde a mensagem, e a deduplicação ficaria em memória.
- **Redis, fila gerenciada ou função serverless.** Um serviço novo para operar e proteger, e mais um lugar por onde o texto passaria.
- **Provedor intermediário (BSP).** Painel e reenvio prontos, com mensalidade ou acréscimo por mensagem, e um operador a mais na LGPD.
