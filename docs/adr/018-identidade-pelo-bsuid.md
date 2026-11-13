# ADR-018 — Identidade do WhatsApp pelo BSUID, com o número só como reserva

Proposto em 2026-11-12 e aceito no mesmo dia, na Etapa 18.0, com a D-12 alterada (seções 30.3 e 30.7 do SDD).

## Contexto

Desde abril de 2026, os webhooks da Meta trazem o identificador do usuário no escopo da empresa (BSUID), em `messages[].from_user_id` e `contacts[].user_id`, no formato `BR.` seguido de até 128 caracteres. Quem adota nome de usuário pode chegar sem o número de telefone no webhook, e a Meta pede que a integração funcione assim. Desde julho de 2026, a Graph API aceita o envio pelo BSUID, no campo `recipient`. O BSUID muda quando a pessoa troca de número, e a Meta avisa com um evento `system` que traz o anterior.

A proposta era não guardar o número. Na revisão da Etapa 18.0, a decisão foi guardar os dois e usar só o BSUID como verdade: o envio pelo BSUID é recente, e o número cobre uma recusa dele.

## Decisão

- O contato do WhatsApp é identificado pelo BSUID, em `whatsapp_contacts.identity`. Sem BSUID, a identidade de reserva é `phone:<número>`.
- O número, quando a Meta o envia, fica em `whatsapp_contacts.phone`. Ele só sai do banco para a porta de envio, quando a Meta recusa o envio pelo BSUID com o código 100, e nunca vai para log, rastro, métrica, console ou exportação.
- O envio usa `recipient` com o BSUID. Os logs levam o HMAC da chave interna do contato com `PSEUDONYM_KEY`.
- Um evento `user_changed_user_id` ou `user_changed_number` troca a identidade do contato.
- Nome de perfil e nome de usuário não são gravados.

## Consequências

- O Atrium responde mesmo quando o número não vem no webhook.
- O número continua no banco enquanto o contato existir: um vazamento do banco expõe números. A retenção de 30 dias e o APAGAR DADOS limitam o prazo.
- O BSUID e o número são dados pessoais: valem a retenção da seção 30.9.7 e as linhas do inventário.
- O BSUID só funciona com números do mesmo portfólio da Meta. Trocar de portfólio perde o vínculo com as conversas, que são curtas de propósito.

## Alternativas

- **Só o BSUID, sem o número.** Era a proposta. Fica sem reserva se o envio pelo BSUID falhar.
- **Só o `wa_id`, que é o número.** Funciona com integrações antigas, mas falha para quem adotou nome de usuário.
- **O número cifrado.** Exige chave e rotação para um dado de reserva.
