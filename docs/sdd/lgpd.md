# LGPD

Parte da [especificação do Atrium](../sdd.md). A numeração das seções é a do documento completo.

## 11. LGPD

Esta seção aplica a Lei nº 13.709/2018 ao Atrium. Na versão 1, contas, conversas e pedidos usam apenas dados fictícios, e não há titular real. O desenho mesmo assim é o de um sistema real: finalidade, minimização, direitos, retenção, auditoria e incidentes. Esta seção, com os documentos listados em 11.11, é o tratamento de LGPD da versão 1. Ela é desenho técnico, não parecer jurídico. Se pessoas reais passarem a se cadastrar, a revisão jurídica volta a ser necessária antes disso.

### 11.1 Papéis

| Papel | Quem |
|---|---|
| Controlador | A pessoa que opera a implantação, em nome do hospital fictício |
| Encarregado, art. 41 | A mesma pessoa, com contato publicado na página Privacy por `PRIVACY_CONTACT_EMAIL` |
| Operadores | Railway (hospedagem e banco), Vercel (entrega do frontend e rewrite), Google (API Gemini), LangChain (LangSmith) |
| Titulares | Visitantes convidados e membros cadastrados |

### 11.2 Princípios aplicados ao desenho

| Princípio, art. 6º | Como o desenho cumpre |
|---|---|
| Finalidade e adequação | Cada dado tem um propósito no inventário da seção 11.3. Campos sem propósito não são coletados. |
| Necessidade | Só nome e e-mail são obrigatórios. Motivo da visita é uma lista fechada, sem texto livre. Mensagens sobre saúde não são gravadas. |
| Livre acesso | Exportação imediata em JSON na página da conta |
| Qualidade dos dados | Correção do perfil na página da conta e revisão do resumo antes do cadastro |
| Transparência | Aviso de Privacidade versionado, avisos no momento da coleta e aviso permanente de que o assistente é uma IA |
| Segurança e prevenção | Seções 10 e 11.8 |
| Não discriminação | O tipo de visitante só personaliza respostas públicas. Não muda acesso nem limite. |
| Responsabilização | Inventário, RIPD, registros de consentimento, auditoria e registro de incidentes |

### 11.3 Inventário de tratamento

O inventário completo vive em `docs/privacy/ropa.md`, cumprindo o art. 37. A tabela é o resumo.

| Dado | Finalidade | Base legal | Onde fica |
|---|---|---|---|
| Nome, e-mail, hash da senha | Conta e entrada | Execução de contrato, art. 7º, V | PostgreSQL |
| Telefone, opcional | Contato do perfil | Execução de contrato, art. 7º, V | PostgreSQL |
| Tipo de visitante e motivo da visita, opcionais | Personalizar respostas | Consentimento específico e destacado, art. 11, I | PostgreSQL |
| Conversas de membro | Histórico pedido pelo titular | Execução de contrato, art. 7º, V | PostgreSQL |
| Conversas de convidado | Responder à pergunta feita | Procedimento a pedido do titular, art. 7º, V | PostgreSQL |
| Texto da pergunta enviado ao Gemini | Classificar e responder | O mesmo da conversa | Google, de forma transitória, conforme os termos do provedor |
| Conversas usadas para melhoria | Avaliar e melhorar o assistente | Consentimento, art. 7º, I | PostgreSQL e conjuntos de avaliação sem identificação |
| Rastros de IA mascarados | Qualidade e diagnóstico | Legítimo interesse, art. 7º, IX, com teste documentado em `docs/privacy/lia.md` | LangSmith |
| HMAC do IP, user agent | Segurança e limite de taxa | Legítimo interesse, art. 7º, IX | PostgreSQL |
| Registros de consentimento | Provar o consentimento | Cumprimento de obrigação, art. 8º, §2º | PostgreSQL |
| Auditoria de acesso de admin | Responsabilização | Legítimo interesse, art. 7º, IX | PostgreSQL |

### 11.4 Dado sensível de saúde

Num hospital, a pessoa pode contar algo sobre a própria saúde mesmo sem ser perguntada. O desenho reduz esse risco em camadas:

1. O compositor de mensagens mostra "Não compartilhe dados de saúde. O Atrium não dá orientação médica." antes da primeira pergunta.
2. Uma mensagem classificada como `medical_advice` tem o conteúdo substituído antes de ser gravada. O histórico mostra que a mensagem não foi guardada, e por quê.
3. O passo de classificação é rastreado no LangSmith só com metadados. A pergunta original nunca chega ao LangSmith.
4. O histórico enviado ao modelo é lido do banco, então nunca contém uma mensagem de saúde de um turno anterior.
5. Os campos de perfil que podem indicar saúde são opcionais, fechados em listas e dependem do consentimento específico do art. 11, I.
6. A produção usa um projeto Google com faturamento ativo. Pelos termos do Gemini, conteúdo enviado em serviços gratuitos pode ser usado pelo Google para melhorar produtos. O nível gratuito fica restrito a dados sintéticos no desenvolvimento.

O texto da mensagem ainda passa pelo Gemini para ser classificado. Isso é um tratamento transitório e está declarado no Aviso de Privacidade.

### 11.5 Direitos do titular

| Direito, art. 18 | Como exercer | Prazo |
|---|---|---|
| Confirmação e acesso | `GET /v1/me/export` na página da conta | Imediato, formato simplificado do art. 19, I |
| Correção | `PATCH /v1/me` | Imediato |
| Anonimização, bloqueio ou eliminação | `DELETE /v1/me` ou pedido no canal | Imediato pela conta. 15 dias pelo canal. |
| Portabilidade | A exportação em JSON legível por máquina | Imediato |
| Informação sobre compartilhamento | Lista de operadores no Aviso de Privacidade | Sempre visível |
| Informação sobre não consentir | Texto ao lado de cada consentimento opcional | Sempre visível |
| Revogação do consentimento | Interruptores em Account, Privacy | Imediato |
| Oposição e revisão | Pedido no canal | 15 dias |

Pedidos feitos pelo canal geram uma linha em `data_subject_requests` com `due_at` em 15 dias corridos. O painel do admin mostra os pedidos atrasados primeiro. Convidados sem conta usam o canal, porque a API não consegue provar quem é o dono de uma conversa anônima depois que o cookie se perde.

A exportação contém perfil, consentimentos com versões, conversas com mensagens e citações, e feedback. Ela não contém hashes, ids internos de rastro nem dados de outros titulares.

### 11.6 Retenção e eliminação

A tarefa agendada `retention-job` roda todo dia às 06:00 UTC na Railway e executa `python -m app.scripts.retention`. Cada regra é uma função testada.

| Dado | Retenção |
|---|---|
| Conta e perfil | Até a exclusão, ou 24 meses sem entrar. Uma conta inativa é eliminada. |
| Conversas de membro | 12 meses a partir da última mensagem, ou até a exclusão da conta |
| Conversas de convidado | 30 dias |
| Sessão de cadastro e transcrição | Apagada na conclusão, no abandono ou em 24 horas |
| Sessões de autenticação | Apagadas 14 dias depois de expirar ou de serem revogadas |
| Janelas de limite de taxa | 48 horas |
| Registros de consentimento | Enquanto a conta existir |
| Auditoria | 2 anos, sem e-mail nem conteúdo |
| Pedidos de titular | 2 anos depois de fechados |
| Registro de incidentes | 5 anos |
| Rastros no LangSmith | Retenção padrão curta do plano, sem identificador direto |
| Logs de aplicação | Retenção da plataforma, sem dado pessoal direto |
| Backups do banco | Ciclo da plataforma. Um dado eliminado some dos backups quando eles expiram. |

`DELETE /v1/me` revoga as sessões e apaga, numa transação, consentimentos, sessões de cadastro, feedback, mensagens, conversas e o usuário. A auditoria grava `account.delete` só com o id. Os rastros do LangSmith usam um pseudônimo derivado do id do usuário com uma chave secreta, então perdem o vínculo com a pessoa quando a conta some.

O Marco Civil da Internet, art. 15, obriga provedores de aplicação constituídos como pessoa jurídica, com fins econômicos, a guardar registros de acesso por 6 meses. Uma implantação de estudo não se enquadra. Se o projeto virar produto, os registros de acesso passam a ser guardados por 6 meses num local com acesso restrito.

### 11.7 Transferência internacional

Railway, Vercel, Google e LangChain tratam dados fora do Brasil. A transferência se apoia no art. 33, com as cláusulas contratuais dos provedores, conforme a Resolução CD/ANPD nº 19/2024. O Aviso de Privacidade lista cada provedor, o país e a finalidade. O LangSmith usa a região padrão dos Estados Unidos, salvo decisão em aberto D-2.

### 11.8 Segurança dos dados

- TLS em todos os trechos: navegador para Vercel, Vercel para Railway e Railway para provedores.
- Senhas com argon2id. Tokens de sessão com hash. IP com HMAC.
- Acesso ao banco de produção só pela rede privada da Railway e por quem opera o projeto.
- Admin vê conversas pseudonimizadas. Revelar a identidade exige um motivo, gravado como `identity.reveal`.
- O inspetor de qualidade só mostra conteúdo de conversas de convidados e de membros com o consentimento de melhoria. As demais aparecem só nos agregados.
- Logs e rastros passam por redação antes de sair do processo, seções 18.1 e 18.4.
- O frontend não carrega scripts nem fontes de terceiros. As fontes são servidas pela própria origem, então o IP do visitante não vai para um serviço de fontes.

### 11.9 Cookies

Só existem cookies estritamente necessários: `atrium_session` e `atrium_guest`. O frontend guarda a preferência de movimento reduzido no `localStorage`, que não sai do navegador. Não há cookie de análise nem de publicidade, então não há banner de consentimento de cookies. A página Privacy explica os dois cookies, conforme o guia de cookies da ANPD.

### 11.10 Incidentes

O roteiro fica em `docs/privacy/incident-playbook.md`:

1. Conter: revogar chaves, sessões ou acessos afetados.
2. Avaliar o risco aos titulares, com dados afetados, volume e probabilidade de dano.
3. Comunicar a ANPD e os titulares em até 3 dias úteis quando o incidente puder gerar risco ou dano relevante, conforme a Resolução CD/ANPD nº 15/2024.
4. Registrar o incidente, mesmo sem comunicação, e guardar o registro por 5 anos.

### 11.11 Documentos de privacidade

| Documento | Caminho | Quando |
|---|---|---|
| Aviso de Privacidade, em português, versionado | `/privacy` no frontend | Junto com a implementação |
| Termos de Uso, em português | `/terms` no frontend | Junto com a implementação |
| Inventário de tratamento | `docs/privacy/ropa.md` | Junto com a implementação |
| Relatório de impacto, art. 38 | `docs/privacy/ripd.md` | Junto com a implementação, com dados fictícios |
| Teste de legítimo interesse | `docs/privacy/lia.md` | Junto com a ligação do LangSmith |
| Roteiro de incidentes | `docs/privacy/incident-playbook.md` | Junto com a implementação |

A versão do Aviso e dos Termos é a constante `LEGAL_DOCUMENT_VERSION` da API. O frontend a lê em `GET /v1/legal/versions`. Uma nova versão exige novo aceite na próxima entrada do membro.

