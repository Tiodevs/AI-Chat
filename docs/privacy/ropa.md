# Inventário de tratamento — Atrium

Registro das operações de tratamento, art. 37 da Lei nº 13.709/2018. É desenho técnico da versão 1, não parecer jurídico. Na versão 1 os dados são fictícios. Se pessoas reais passarem a usar o Atrium, a revisão jurídica volta a ser necessária antes disso.

O resumo está na seção 11.3 do SDD. Este documento é a versão completa. Uma mudança num dado, numa finalidade ou num prazo atualiza os dois na mesma pull request.

## Agentes

| Papel | Quem |
|---|---|
| Controlador | A pessoa que opera a implantação, em nome do Harborlight General Hospital, fictício |
| Encarregado | A mesma pessoa, com contato publicado em `/privacy` por `PRIVACY_CONTACT_EMAIL` |
| Operadores | Railway, Vercel, Google, LangChain e Meta (WhatsApp), na tabela de compartilhamento abaixo |
| Titulares | Visitantes convidados e membros cadastrados |

## Operações

| Dado | Titular | Finalidade | Base legal | Onde fica | Quem acessa | Retenção |
|---|---|---|---|---|---|---|
| Nome, e-mail, hash da senha | Membro | Conta e entrada | Execução de contrato, art. 7º, V | `users` | O titular. Admin só pseudonimizado. | Até a exclusão, ou 24 meses sem entrar |
| Telefone, opcional | Membro | Contato do perfil | Execução de contrato, art. 7º, V | `users.phone` | O titular | Até a exclusão |
| Tipo de visitante e motivo da visita, opcionais | Membro | Personalizar respostas públicas | Consentimento específico e destacado, art. 11, I | `users.visitor_type`, `users.visit_reason` | O titular | Apagados ao revogar a personalização, ou na exclusão |
| Conversas de membro | Membro | Histórico pedido pelo titular | Execução de contrato, art. 7º, V | `conversations`, `messages`, `feedback` | O titular. Admin só com o consentimento de melhoria. | 12 meses depois da última mensagem, ou até a exclusão |
| Conversas de convidado | Convidado | Responder à pergunta feita | Procedimento a pedido do titular, art. 7º, V | `conversations`, `messages`, `guest_keys` | Quem tem o cookie `atrium_guest`. Admin pseudonimizado. | 30 dias |
| Texto da pergunta enviado ao Gemini | Ambos | Classificar e responder | O mesmo da conversa | Google, transitório | O provedor, conforme os termos dele | Termos do provedor |
| Conversas usadas para melhoria | Membro | Avaliar e melhorar o assistente | Consentimento, art. 7º, I | PostgreSQL e conjuntos de avaliação sem identificação | Admin | Enquanto o consentimento valer |
| Rastros de IA mascarados | Ambos | Qualidade e diagnóstico | Legítimo interesse, art. 7º, IX, teste em `lia.md` | LangSmith, Estados Unidos | Admin | Retenção curta do plano, sem identificador direto |
| Sessão de cadastro e transcrição | Visitante | Concluir o cadastro por conversa | Procedimento a pedido do titular, art. 7º, V | `registration_sessions` | O próprio visitante | Apagada na conclusão, no abandono ou em 24 horas |
| Sessões de autenticação | Membro | Manter a entrada | Execução de contrato, art. 7º, V | `auth_sessions`, só o SHA-256 do segredo | Ninguém lê o segredo | 14 dias depois de expirar ou de ser revogada |
| HMAC do IP, user agent | Ambos | Segurança e limite de taxa | Legítimo interesse, art. 7º, IX | `rate_limit_windows`, `auth_sessions.user_agent` | Ninguém lê o IP cru | 48 horas para as janelas |
| Registros de consentimento | Membro | Provar o consentimento | Cumprimento de obrigação, art. 8º, §2º | `consent_records` | O titular, na exportação | Enquanto a conta existir |
| Auditoria de admin e de conta | Ambos | Responsabilização | Legítimo interesse, art. 7º, IX | `audit_events`, sem e-mail nem conteúdo | Operador | 2 anos |
| Pedidos de titular | Qualquer pessoa | Atender os direitos do art. 18 | Cumprimento de obrigação, art. 18 | `data_subject_requests` | Admin | 2 anos depois de fechado |
| Registro de incidentes | Afetados | Responsabilização e comunicação | Cumprimento de obrigação, art. 48 | Fora do sistema, conforme `incident-playbook.md` | Operador | 5 anos |
| BSUID e datas do contato do WhatsApp | Quem escreve pelo WhatsApp | Responder e manter a conversa | Procedimento a pedido do titular, art. 7º, V | `whatsapp_contacts.identity` | Ninguém pela interface; logs só com o HMAC | 30 dias depois da última mensagem, ou na hora com APAGAR DADOS |
| Número de telefone do WhatsApp, quando a Meta envia | Quem escreve pelo WhatsApp | Reserva de envio quando a Meta recusa o envio pelo BSUID (D-12) | Art. 7º, V | `whatsapp_contacts.phone` | Só o enviador; nunca a equipe, logs, rastros ou exportação | Com o contato |
| Conversas do WhatsApp | Quem escreve pelo WhatsApp | Responder à pergunta e ao atendimento | Art. 7º, V | `conversations` com `channel = whatsapp`, `messages` | A equipe só no atendimento assumido, sem número | Com o contato |
| Caixas de entrada e de saída do WhatsApp | Quem escreve pelo WhatsApp | Receber sem duplicar e entregar com nova tentativa | Art. 7º, V | `whatsapp_inbound_events`, `whatsapp_outbound_messages` | Ninguém pela interface | Texto apagado ao processar e no status final; linhas em 7 dias |

A tarefa `retention-job` aplica os prazos todo dia às 06:00 UTC (`python -m app.scripts.retention`). Cada regra é uma função testada em `apps/api/tests/integration/test_retention.py`. Os prazos em meses viram dias corridos: 12 meses são 365 dias e 24 meses são 730. Uma conta de admin não é eliminada por inatividade, porque a remoção de admin segue a seção 10.5.

## Compartilhamento e transferência internacional

| Operador | País | Finalidade | Dados |
|---|---|---|---|
| Railway | Estados Unidos | Hospedagem da API, do banco e da tarefa de retenção | Todos os da tabela de operações que ficam no PostgreSQL |
| Vercel | Estados Unidos | Entrega do frontend e rewrite para a API | Tráfego em trânsito, sem armazenamento da resposta |
| Google, API Gemini | Estados Unidos | Classificar, responder e entender o cadastro | Texto da pergunta e mensagens do cadastro, transitórios |
| LangChain, LangSmith | Estados Unidos | Rastros de IA mascarados | O que a política de rastro permite, seção 18.4 |
| Meta, WhatsApp Business Platform (Cloud API) | Estados Unidos | Entregar as mensagens do canal WhatsApp (seção 30) | Mensagens, BSUID e número de quem escreve, pelo prazo dos termos da Meta |

A transferência se apoia no art. 33, com as cláusulas contratuais dos provedores, conforme a Resolução CD/ANPD nº 19/2024.

## Medidas de segurança

Seções 10 e 11.8 do SDD: TLS em todos os trechos, argon2id nas senhas, hash nos tokens, HMAC no IP, admin com dados pseudonimizados e revelação de identidade auditada, logs e rastros redigidos antes de sair do processo.
