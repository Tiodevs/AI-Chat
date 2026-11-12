---
paths:
  - "apps/api/app/**/handoff*.py"
  - "apps/api/app/**/attendance*.py"
  - "apps/api/app/**/attendant*.py"
  - "apps/api/app/**/realtime*.py"
  - "apps/api/app/domain/redaction.py"
  - "apps/api/app/scripts/attendants.py"
  - "apps/api/app/scripts/attendance_dev.py"
  - "apps/web/src/features/attendance/**"
  - "apps/web/src/features/ask/**"
  - "apps/web/src/components/patterns/handoff*"
  - "apps/web/src/components/patterns/attendant*"
  - "apps/web/src/components/patterns/queue*"
  - "apps/web/src/components/patterns/presence*"
  - "apps/web/src/components/patterns/redact*"
---

# Atendimento humano

A especificação é a seção 29 do SDD (`docs/sdd/atendimento-humano.md`). As regras abaixo vêm das seções 29.8 e 29.9 e valem para todo código do atendimento.

- O texto do atendimento nunca vai ao Gemini nem ao LangSmith, nem como histórico de uma pergunta posterior. Leituras para o modelo filtram `handoff_id IS NULL`. Nenhuma rota do atendimento recebe o provedor de chat, o de embedding ou o `FeedbackSink`.
- Quem não é dono da conversa, ou quem não assumiu o atendimento, recebe 404, igual a um id inexistente. Confira dono, papel e atribuição em cada pedido e em cada tique do fluxo.
- A fila, o evento `queue` e a lista de encerrados não têm conteúdo, nome, e-mail, telefone, tipo de visitante nem tipo de sujeito. O rótulo vem do HMAC do id do atendimento.
- A carga do `pg_notify('atrium_handoff', ...)` leva só `handoff_id`, `seq` e `kind`. O `NOTIFY` roda dentro da transação que grava. O fluxo nunca confia na carga: ele lê do banco com a própria autorização.
- A mensagem do visitante passa por `redact_identifiers` antes de gravar e antes do `NOTIFY`. A da equipe não passa.
- Cada ação da equipe grava o evento de auditoria na mesma transação: `handoff.take`, `handoff.release`, `handoff.close`, `handoff.message_redact` e `handoff.view`. O `reason` guarda o motivo ou a categoria, nunca conteúdo nem e-mail.
- Logs, spans e métricas levam ids, rótulos e enums. Nunca texto de mensagem.
- O papel `attendant` só muda pelo script `app.scripts.attendants`. Nenhuma rota da web concede papel.
- No frontend, a mensagem do atendimento sai como texto puro, com `white-space: pre-wrap`: sem Markdown, sem HTML, sem link clicável e sem `dangerouslySetInnerHTML`. O título da aba do console mostra só a contagem.
- Texto visível fica em `apps/web/src/i18n/pt.ts` e em `apps/api/app/prompts/handoff.py`.
