# ADR-017 — WhatsApp pela Cloud API, com caixa de entrada e caixa de saída no PostgreSQL

Proposto em 2026-11-12 e aceito no mesmo dia, na Etapa 18.0 (seção 30.2 do SDD).

## Contexto

O canal WhatsApp recebe as mensagens por um webhook da Meta. A Meta exige HTTP 200 e, sem ele, tenta de novo com frequência decrescente por até 7 dias, o que pode duplicar notificações. A pergunta à IA leva até 12 segundos no p95 (seção 5.3), e o envio da resposta depende da Graph API, que pode responder 429 ou 5xx. A versão 1 tem uma réplica da API (ADR-012), o PostgreSQL é o único armazenamento (ADR-002) e o `RealtimeBroker` já avisa as mudanças do atendimento humano (ADR-016).

## Decisão

- A rota `POST /v1/whatsapp/webhook` confere a assinatura `X-Hub-Signature-256` sobre o corpo cru, grava cada evento em `whatsapp_inbound_events` com a chave única `event_key` e responde 200. Nenhum trabalho de negócio acontece antes da resposta.
- Um laço no `lifespan` acorda pelo aviso do webhook do mesmo processo, por um aviso do atendimento ou a cada 2 segundos. Ele pega um evento por vez com `UPDATE ... WHERE id = (SELECT ... FOR UPDATE SKIP LOCKED)`, em ordem por pessoa, chama o pipeline da seção 7.1 ou o atendimento da seção 29, e grava a resposta, as saídas e o fim do evento numa transação só.
- Toda mensagem a enviar é uma linha em `whatsapp_outbound_messages`. O enviador reserva a linha por 2 minutos, envia e grava o `wamid`, ou agenda a próxima tentativa com espera crescente. Os webhooks de status atualizam a linha pelo `wamid`.
- O atendimento chega ao WhatsApp por um repasse: o laço lê os atendimentos do canal com mensagem da equipe ou status ainda não repassados e grava as saídas na mesma transação que avança o cursor `whatsapp_handoff_relay`. O código do console e da varredura não muda.
- A Graph API fica atrás da porta `MessagingChannel`, com o adaptador `MetaCloudApiChannel` e o `FakeMessagingChannel` dos testes.

## Consequências

- Uma notificação repetida pela Meta não gera segunda resposta.
- Uma falha da Graph API ou um reinício não perde a resposta: a linha continua `pending`.
- Nenhum serviço novo. Funciona com uma réplica e com várias: outra réplica acha o evento em até 2 segundos.
- O envio é pelo menos uma vez: um processo que cai entre o aceite da Meta e o commit do `wamid` pode enviar de novo.
- O texto fica no banco de entrada só até o evento terminar, e no de saída só até o status final.

## Alternativas

- **Responder ao webhook depois de gerar a resposta.** A Meta repetiria a notificação, e o Atrium responderia duas vezes.
- **Tarefa de fundo do FastAPI sem gravar antes.** Um reinício perde a mensagem, e a deduplicação ficaria em memória.
- **Gravar a saída na mesma transação do console e da varredura.** Exigiria mudar o código da seção 29 em cada transição. O repasse por cursor dá a mesma garantia sem tocar nele.
- **Um `LISTEN` próprio para o canal.** Mais uma conexão fora do pool para ganhar no máximo 2 segundos numa segunda réplica.
- **Redis, fila gerenciada ou função serverless.** Um serviço novo para operar e proteger, e mais um lugar por onde o texto passaria.
- **Provedor intermediário (BSP).** Painel e reenvio prontos, com mensalidade ou acréscimo por mensagem, e um operador a mais na LGPD.
