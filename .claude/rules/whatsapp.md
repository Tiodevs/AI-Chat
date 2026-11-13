---
paths:
  - "apps/api/app/**/whatsapp*.py"
  - "apps/api/app/ports/messaging.py"
  - "apps/api/app/adapters/fake_messaging.py"
  - "apps/api/alembic/versions/0011_whatsapp.py"
  - "apps/api/tests/**/test_whatsapp*.py"
---

# Canal WhatsApp

A especificação é a seção 30 do SDD (`docs/sdd/whatsapp.md`), com o ADR-017 e o ADR-018. As regras abaixo vêm das seções 30.4, 30.8 e 30.9 e valem para todo código do canal.

- A rota do webhook só confere a assinatura sobre o corpo cru, grava a caixa de entrada e responde 200. Nada de modelo, rede ou regra de negócio antes da resposta.
- A isenção de `Origin` vale só para `WEBHOOK_PATH`. Nenhuma outra rota entra nela.
- Nenhuma transação fica aberta durante a chamada ao modelo ou à Graph API. A resposta, as saídas e o fim do evento são gravados numa transação só.
- Tudo que sai passa pela caixa de saída e pela porta `MessagingChannel`. Fora da janela de 24 horas, nada sai. O Atrium nunca inicia conversa.
- A identidade é o BSUID. O número fica só em `whatsapp_contacts.phone`, como reserva de envio, e nunca vai para log, span, métrica, LangSmith, console nem exportação.
- O texto do atendimento nunca vai ao modelo, também no WhatsApp: o histórico sai de `ai_messages`, e a mensagem do visitante durante o atendimento vai para o `HandoffService`, que remove os identificadores.
- Mídia não é baixada. O id da mídia nem é gravado.
- Logs, spans e métricas levam enums, contagens e códigos de erro. Nunca texto, BSUID ou número.
- Testes automáticos nunca chamam a Meta. Use o `FakeMessagingChannel`.
- Texto visível ao visitante fica em `apps/api/app/prompts/whatsapp.py`. Título de botão tem até 20 caracteres.
