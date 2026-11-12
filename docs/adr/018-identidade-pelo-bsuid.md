# ADR-018 — Identidade do WhatsApp pelo BSUID, sem guardar o telefone

Proposto em 2026-11-12, em revisão na Etapa 18.0 (seções 30.3 e 30.7 do SDD).

## Contexto

Desde abril de 2026, os webhooks da Meta trazem o identificador do usuário no escopo da empresa (BSUID), em `messages[].from_user_id` e `contacts[].user_id`, no formato `BR.` seguido de até 128 caracteres. Quem adota nome de usuário pode chegar sem o número de telefone no webhook, e a Meta pede que a integração funcione assim. Desde julho de 2026, a Graph API aceita o envio pelo BSUID, no campo `recipient`. O BSUID muda quando a pessoa troca de número, e a Meta avisa com um evento `system` que traz o anterior.

## Decisão

O contato do WhatsApp é identificado só pelo BSUID, em `whatsapp_contacts.bsuid`. O número de telefone, o nome de perfil e o nome de usuário não são gravados em nenhuma coluna, log, rastro ou métrica. O envio usa `recipient` com o BSUID. Os logs levam o HMAC do BSUID com `PSEUDONYM_KEY`. Um evento `user_changed_user_id` ou `user_changed_number` troca o BSUID do contato.

## Consequências

- O Atrium responde sem saber o telefone de ninguém, e um vazamento do banco não expõe números.
- O BSUID continua sendo dado pessoal pseudonimizado: vale a retenção de 30 dias da seção 30.9.7.
- O BSUID só funciona com números do mesmo portfólio da Meta. Trocar de portfólio perde o vínculo com as conversas, que são curtas de propósito.
- Não dá para buscar a conversa de alguém pelo telefone. Um pedido de titular pelo canal de privacidade precisa de outro caminho de prova, e o comando APAGAR DADOS cobre a eliminação.

## Alternativas

- **Guardar o `wa_id`, que é o telefone.** Funciona com integrações antigas, mas grava um dado que o Atrium não precisa e falha para quem adotou nome de usuário.
- **Guardar o telefone cifrado.** Ainda exige chave, rotação e justificativa para um dado sem uso.
