# Documento de especificação de software — Atrium

| | |
|---|---|
| Produto | Atrium, assistente público para visitantes do Harborlight General Hospital |
| Repositório | AI-Chat |
| Status | Aprovado 1.0 |
| Data | 2026-10-25 |
| Público | Uma pessoa desenvolvedora aprendendo sistemas de IA para produção |
| Idioma desta especificação | Português |
| Idioma do produto | Português do Brasil na interface, nos documentos e nas respostas. Código, rotas e identificadores em inglês |

Este documento é a especificação de construção. A implementação segue o que está aqui. Quando uma mudança posterior contradisser este documento, o documento é atualizado na mesma mudança. Decisões estruturais ficam registradas como ADRs na seção 24.

## 1. Propósito

Atrium é um sistema de estudo para um produto web em que a IA vem primeiro. Visitantes e pacientes de um hospital fictício podem fazer perguntas públicas e criar uma conta por uma conversa guiada ou por um formulário comum.

O hospital, as pessoas, os telefones e os documentos são inventados. A engenharia ao redor deles tem forma de produção:

- divisão clara de responsabilidades
- respostas aumentadas por recuperação, com citações verificáveis
- testes automáticos que não chamam um modelo ao vivo
- avaliação contínua da qualidade da IA
- observabilidade capaz de explicar uma resposta ruim depois que ela acontece
- tratamento de dados pessoais conforme a LGPD
- uma interface com design system próprio e movimento com propósito

## 2. Decisões já tomadas

| Tema | Decisão |
|---|---|
| Para quem é | Pacientes e visitantes. Informação pública do hospital e cadastro. |
| Cadastro | Um chat guiado coleta o perfil e cria a conta. Um formulário comum fica sempre disponível, inclusive no meio do chat. |
| Backend | Python com FastAPI |
| Frontend | React com TypeScript, construído com Vite, como aplicação de página única |
| Fluxos de IA | LangChain para o pipeline de perguntas e LangGraph para o cadastro |
| Acesso ao modelo | A aplicação depende de portas próprias de chat e de embedding. Gemini é o adaptador padrão. Os testes usam falsos. |
| Modelo de chat | `gemini-2.5-flash`, substituível por `CHAT_MODEL`. O `gemini-3.8-flash` do plano gratuito esgota em 20 pedidos por dia. |
| Modelo de embedding | `gemini-embedding-2` com 768 dimensões, substituível por `EMBEDDING_MODEL` |
| RAG | PostgreSQL com pgvector, busca híbrida vetorial e por texto completo |
| Testes | Pytest na API. Vitest, Testing Library e Playwright no frontend. |
| CI/CD | GitHub Actions testa, publica em development e, com aprovação, publica em produção |
| Observabilidade | Logs estruturados, rastros OpenTelemetry, métricas Prometheus com Grafana e LangSmith para os fluxos de IA |
| Execução local | A API e o frontend rodam direto na máquina. Docker não é necessário no desenvolvimento local. |
| Banco fora da CI | PostgreSQL da Railway com a extensão `vector`, no ambiente `development`, usado pelos aplicativos locais |
| Produção | Frontend na Vercel. API, PostgreSQL, tarefa agendada, Prometheus e Grafana na Railway. |
| Documentos | Um corpus fictício semeado. Um admin pode incluir, substituir e arquivar documentos na interface. |
| Dados pessoais | Tratamento conforme a LGPD, seção 11 |
| Interface | Design system escuro derivado da imagem de referência, com Radix UI, Lucide, Tailwind e shadcn/ui. Animações com GSAP. Seções 14 a 16. |
| Profundidade | Esta especificação tem detalhe suficiente para implementar. |

### 2.1 Escolhas confirmadas

Estas escolhas não estavam no formulário de perguntas. Elas mantêm a primeira versão ensinável e segura. Foram confirmadas na revisão final, em 2026-10-25. Uma mudança posterior atualiza este documento na mesma mudança.

| Escolha | Por que é o padrão |
|---|---|
| Nome do produto **Atrium**. Hospital **Harborlight General Hospital**, na cidade fictícia de **Port Meridian**. | O repositório pode continuar `AI-Chat`. O produto precisa de um nome estável para prompts, documentos e interface. |
| Interface, documentos do hospital, prompts visíveis e respostas em português do Brasil. | É a língua de quem usa o produto. Código, rotas, enums e os prefixos de embedding exigidos pelo Gemini continuam em inglês. |
| Contas, conversas e pedidos usam só dados fictícios. | Não há titular real na versão 1. A seção 11 trata esses dados como um sistema real trataria, e esse desenho basta. |
| Sem domínio próprio. | A origem de produção é a URL da Vercel. `WEB_ORIGIN` aponta para ela. |
| Perguntas funcionam sem conta. O cadastro é opcional e guarda o histórico. | Uma página pública de hospital responde ao visitante antes de pedir que ele se cadastre. |
| Admin é uma conta de operação criada por um script de implantação. O chat público não pode criar um admin. | A gestão de documentos precisa de um operador. Cadastro público de admin seria uma falha de privilégio. |
| As transições de estado do cadastro são Python puro, na camada de domínio. O Gemini só extrai campos e formula a próxima pergunta. | Um modelo não decide que uma conta existe. |
| A senha vai para um endpoint próprio e é armazenada só como hash argon2id. | A transcrição enviada ao modelo não contém senha. |
| O cadastro coleta o mínimo. Campos que podem revelar saúde são opcionais, fechados em listas e dependem de consentimento específico. | Minimização da LGPD, art. 6º, III, e cuidado com dado sensível, art. 11. |
| Uploads aceitos: Markdown, texto puro e PDF, até 10 MB. Os bytes do arquivo ficam no PostgreSQL. | Um banco basta para este corpus. Um bucket pode esperar. |
| O navegador fala só com a origem do frontend. Um rewrite da Vercel encaminha `/backend/*` para o FastAPI. Localmente, o proxy do Vite faz o mesmo. | Vercel e Railway são sites diferentes. A mesma origem mantém o cookie de sessão primário e dispensa CORS no tráfego normal. |
| Os aplicativos locais usam o banco `development` da Railway. Eles não usam o banco de produção. | Um experimento no laptop não reescreve o corpus publicado. |
| A CI pode subir um PostgreSQL `pgvector/pgvector` no runner do GitHub. | O laptop continua sem Docker. O pipeline ainda testa consultas vetoriais de verdade. |
| A exclusão de conta e a exportação de dados entram na primeira versão. Entrega de e-mail, verificação de e-mail e recuperação de senha ficam de fora. | Exclusão e exportação são direitos do titular. Um provedor de e-mail é outro projeto. |
| O LangGraph executa o grafo do cadastro sem checkpointer. O serviço carrega e grava o estado no PostgreSQL. | O serviço continua dono da persistência e da transação. O LangGraph fica só com a orquestração. |
| Prompts vivem no repositório e têm versão. A versão vai para cada mensagem e para cada rastro. | Uma mudança de prompt passa por revisão de código e pode ser comparada em avaliações. |
| Uma réplica da API na versão 1. | Evita corrida em tarefas de fundo e facilita a coleta de métricas. A seção 6.5 trata a escala. |
| LangSmith na região dos Estados Unidos. | Decisão D-2. As duas regiões são transferência internacional para a LGPD. Estados Unidos mantém a primeira versão simples. |

### 2.2 Rastreabilidade com o plano de ação

O plano de ação original pedia os itens abaixo. A tabela mostra onde cada um é atendido.

| Item do plano | Onde está | Situação |
|---|---|---|
| Python com FastAPI | Seções 6 e 12 | Atendido |
| Frontend web | Seção 13, React com Vite | Atendido. Next.js trocado por React nesta revisão. |
| PyTest | Seção 21 | Atendido |
| LangChain no fluxo de IA | Seções 7.1, 7.2 e 17 | Atendido |
| GitHub Actions para CI/CD | Seção 22 | Atendido. A versão 0.2 só fazia CI. A entrega agora é feita pelo GitHub Actions. |
| PostgreSQL com pgvector para RAG | Seções 8 e 7.1 | Atendido |
| Observabilidade, monitoramento, logs e métricas | Seção 18 | Atendido. A versão 0.2 expunha métricas sem coletor, painéis ou alertas. A 0.3 adiciona Prometheus, Grafana, alertas e LangSmith. |
| Padrão MVC | Seção 6.2 | Atendido, com as camadas extras que um sistema de IA exige |
| Hospital com documentos fictícios | Seção 9 | Atendido |
| Cadastro com IA | Seção 7.2 | Atendido |
| Respostas sobre o hospital | Seção 7.1 | Atendido |
| Boas práticas de desenvolvimento com IA | Seções 7, 10.2, 17, 18.4 e 21.2 | Atendido: guardrails, prompts versionados, avaliações, feedback humano, orçamento de custo e degradação controlada |
| LangSmith | Seção 18.4 | Adicionado nesta revisão |
| LGPD | Seção 11 | Adicionado nesta revisão |
| Design system a partir da imagem | Seção 14 | Adicionado nesta revisão |
| Animações com GSAP | Seção 16 | Adicionado nesta revisão |
| Plano de UI/UX | Seção 15 | Adicionado nesta revisão |

## 3. Usuários e o trabalho do produto

### 3.1 Visitante

Um paciente, um visitante ou um acompanhante, no telefone ou no laptop.

Essa pessoa precisa encontrar horários, entradas, estacionamento, departamentos e outros fatos publicados. Ela pode criar uma conta para o assistente lembrar a conversa. Ela não recebe diagnóstico, orientação de medicamento nem acesso a prontuário. O Atrium não tem prontuário.

### 3.2 Admin

A pessoa que opera a implantação. Ela entra com a conta de admin, gerencia documentos, inspeciona a qualidade das respostas e atende pedidos de titulares de dados. Cada leitura de conversa e cada revelação de identidade feita por um admin é gravada no log de auditoria.

### 3.3 Hospital fictício, dito uma vez

O Harborlight General Hospital é um hospital comunitário de 280 leitos, em 410 Cedar Wharf Avenue, Port Meridian. A entrada principal fica de frente para a Cedar Wharf Avenue. A entrada de emergência fica no lado oeste, com acesso pela Harbor Street, e funciona 24 horas. A mesa telefônica é (555) 014-2600. O prefixo 555 é usado porque é reservado para ficção.

A seção 9 é o único catálogo de horários e telefones. Prompts, arquivos de semente e testes tiram os fatos desse catálogo.

## 4. Escopo

### 4.1 Dentro do escopo

- Respostas públicas sobre o corpus publicado, com citações
- Recusa de orientação médica e recusa de perguntas que o corpus não sustenta
- Cadastro por conversa e um formulário que usa o mesmo caminho de conclusão
- Entrada, saída, perfil, histórico de conversas, correção, exportação e exclusão de conta
- Gestão de consentimentos e canal de pedidos do titular
- Retenção automática de dados por uma tarefa agendada
- Upload, substituição, arquivamento, painel de visão geral, visão de qualidade e fila de pedidos de privacidade para o admin
- Semente idempotente do corpus fictício
- Pytest da API, inclusive recuperação contra o pgvector
- Testes de frontend: unidade, componente, ponta a ponta e acessibilidade
- Logs estruturados, rastros OpenTelemetry, métricas Prometheus, painéis e alertas no Grafana
- LangSmith para rastros de IA, feedback e avaliações
- GitHub Actions para CI e para publicação em development e produção
- Design system documentado, com catálogo de componentes
- Movimento com GSAP, com suporte a movimento reduzido
- Canal WhatsApp pela Cloud API da Meta, com resposta da IA e atendimento humano, seção 30

### 4.2 Fora do escopo

Prontuário eletrônico, HL7, FHIR, elegibilidade de convênio, marcação de consulta, pagamentos, SMS, entrega de e-mail, recuperação de senha, interface em vários idiomas, tema claro, aplicativos móveis nativos, busca de políticas só para a equipe, banco vetorial separado, Kubernetes, Docker como requisito do desenvolvimento local, renderização no servidor e plantão com pager. O `docker-compose.yml` da raiz é uma alternativa opcional para subir tudo localmente: o caminho documentado continua sem Docker (NFR-4).

Uma fila, armazenamento de objetos, várias réplicas da API e um ambiente separado de staging são o caminho de escala planejado. Eles não são necessários para a versão 1 funcionar.

## 5. Requisitos

### 5.1 Funcionais

| ID | Requisito |
|---|---|
| FR-1 | Um visitante pode fazer uma pergunta sem conta. |
| FR-2 | Uma resposta que afirma um fato do hospital inclui pelo menos uma citação a um chunk publicado e ativo. |
| FR-3 | Um pedido de diagnóstico, medicamento, dose ou avaliação de sintoma recebe a resposta fixa de orientação médica e não chama o gerador. |
| FR-4 | O sistema se abstém quando a recuperação fica abaixo do piso de similaridade, quando o modelo não cita nada válido, ou quando um telefone no rascunho está ausente do texto recuperado. |
| FR-5 | Um visitante pode concluir o cadastro pela conversa. O assistente pede um campo ausente de cada vez e aceita que campos opcionais sejam pulados. |
| FR-6 | Um visitante pode abrir o formulário a qualquer momento. Os campos já coletados vêm preenchidos. A senha nunca vem preenchida. |
| FR-7 | A senha trafega só pelo endpoint de senha ou pelo endpoint do formulário. Ela é hasheada antes de ser gravada. Ela está ausente de transcrições, logs, rastros e pedidos ao modelo. |
| FR-8 | O cadastro só termina depois do aceite explícito dos Termos e do Aviso de Privacidade e da declaração de maioridade. |
| FR-9 | Um membro pode ler o perfil e as conversas, corrigir o perfil, exportar os dados, gerir consentimentos, sair e excluir a conta. |
| FR-10 | Um admin pode enviar um documento Markdown, texto ou PDF de até 10 MB. |
| FR-11 | Substituir um documento cria uma versão nova. A versão anterior continua pesquisável até a nova chegar a `ready`. Uma ingestão com falha deixa a versão anterior ativa. |
| FR-12 | Arquivar um documento tira ele da recuperação. |
| FR-13 | A semente é idempotente. Um documento cujo checksum não mudou não é embedado de novo. |
| FR-14 | Um visitante pode marcar uma resposta do assistente como útil ou não útil, uma vez. A nota chega ao LangSmith quando a resposta tem rastro. |
| FR-15 | Um admin vê um painel com indicadores, a qualidade das respostas e as conversas recentes. Abrir uma conversa grava um evento de auditoria. |
| FR-16 | Qualquer pessoa pode abrir um pedido de titular pelo canal de privacidade. O admin vê a fila com prazos. |
| FR-17 | Uma mensagem classificada como orientação médica não tem o conteúdo gravado nem enviado ao LangSmith. |
| FR-18 | Um visitante pode interromper uma resposta em andamento. |
| FR-19 | Depois de uma resposta que não ajudou, o visitante pode chamar uma pessoa da equipe. Uma recusa médica nunca oferece o atendimento. |
| FR-20 | Antes de chamar a equipe, o visitante vê o que vai ser lido, por quem e por quanto tempo fica guardado, e confirma. |
| FR-21 | Com o atendimento ativo, as mensagens do visitante vão só para a equipe. O texto do atendimento nunca chega ao Gemini nem ao LangSmith, nem como histórico de uma pergunta posterior. |
| FR-22 | Um atendente ou admin vê a fila sem conteúdo, assume um atendimento que nenhuma outra pessoa assumiu, lê a conversa e responde. Assumir grava `handoff.take`. |
| FR-23 | Visitante e equipe recebem mensagens e mudanças de status em tempo real e, depois de uma reconexão, recebem o que perderam, sem repetir. |
| FR-24 | O visitante encerra o atendimento quando quiser. A equipe encerra com um motivo de uma lista fechada. |
| FR-25 | Identificadores na mensagem do visitante são removidos antes de gravar, e a equipe apaga o conteúdo de uma mensagem com dado sensível, com auditoria. |
| FR-26 | O admin só abre um atendimento encerrado com um motivo, gravado em `handoff.view`. |
| FR-27 | Uma pessoa pode mandar uma pergunta de texto pelo WhatsApp e receber a resposta do mesmo pipeline da seção 7.1, com as fontes. |
| FR-28 | Antes da primeira resposta no WhatsApp, e de novo quando a versão dos documentos legais muda, a pessoa recebe o aviso de que fala com uma IA, o pedido de não mandar dados de saúde e o link do Aviso de Privacidade. |
| FR-29 | No WhatsApp, recusa médica, abstenção e degradação seguem as regras da web, e a pergunta médica não tem o conteúdo gravado. |
| FR-30 | Depois de uma resposta que não ajudou, o WhatsApp oferece o atendimento com botões. A pessoa confirma antes de entrar na fila, e a equipe responde pelo mesmo console da seção 29. |
| FR-31 | Mídia recebida pelo WhatsApp não é baixada nem guardada, e a pessoa recebe a resposta fixa. |
| FR-32 | A pessoa apaga os próprios dados do WhatsApp com o comando APAGAR DADOS e a confirmação por botão. |
| FR-33 | O Atrium nunca inicia conversa no WhatsApp. Ele só responde dentro da janela de 24 horas, sem modelo de mensagem. |

### 5.2 Não funcionais

| ID | Requisito |
|---|---|
| NFR-1 | Os limites de camada da seção 6.2 são verificados por um teste automático de importação, na API e no frontend. |
| NFR-2 | As chaves do Gemini e do LangSmith existem só no processo da API. O navegador nunca as recebe. |
| NFR-3 | A execução padrão dos testes automáticos não faz chamada de rede ao Gemini nem ao LangSmith. |
| NFR-4 | O desenvolvimento local não exige Docker. |
| NFR-5 | A CI roda os testes da API contra PostgreSQL com pgvector. |
| NFR-6 | Cada pedido tem um `request_id`. Logs, rastros OpenTelemetry e rastros do LangSmith o carregam. A API o devolve em `x-request-id`. |
| NFR-7 | Logs e atributos de span excluem corpo de mensagem, corpo de documento, e-mails, telefones, IP cru e segredos. |
| NFR-8 | Os bancos `development` e `production` são ambientes Railway diferentes. |
| NFR-9 | A verificação de prontidão falha quando o banco está inacessível, a extensão `vector` está ausente ou a dimensão do embedding diverge da coluna. |
| NFR-10 | Tamanho do upload, tipo de mídia, a lista de campos do cadastro e a autorização são impostos no servidor. |
| NFR-11 | Toda resposta de `/v1` sai com `Cache-Control: no-store`. |
| NFR-12 | Pedidos que mudam estado exigem `Origin` igual à origem do frontend. |
| NFR-13 | Um orçamento diário de tokens limita o custo do Gemini. Ao estourar, o produto degrada de forma controlada. |
| NFR-14 | A interface cumpre WCAG 2.2 nível AA. |
| NFR-15 | Todo movimento respeita `prefers-reduced-motion` e a preferência salva pelo usuário. |
| NFR-16 | O contrato OpenAPI e os tipos do frontend não divergem. A CI falha quando divergem. |
| NFR-17 | O atendimento humano usa SSE e `POST` pelo rewrite de mesma origem, sem WebSocket e sem operador novo (ADR-015). |
| NFR-18 | Toda leitura de conteúdo pela equipe é autorizada em cada pedido e em cada tique do fluxo. O aviso entre processos leva só ids (ADR-016). |
| NFR-19 | Um fluxo do atendimento dura no máximo 10 minutos e é retomado pelo último `seq`, sem perda. |
| NFR-20 | Pedidos de atendimento, mensagens e fluxos têm limites por sujeito, por IP, por atendente e por processo (seção 29.8). |
| NFR-21 | O webhook do WhatsApp confere a assinatura da Meta antes de interpretar o corpo e responde 200 sem chamar modelo nem rede (ADR-017). |
| NFR-22 | Uma notificação repetida pela Meta não gera segunda resposta. |
| NFR-23 | A identidade de quem escreve pelo WhatsApp é o BSUID. O número, quando a Meta o envia, fica só em `whatsapp_contacts.phone`, como reserva de envio, e nunca vai para log, rastro, métrica, console ou exportação (ADR-018). |
| NFR-24 | A execução padrão dos testes automáticos não faz chamada à Graph API da Meta. |
| NFR-25 | Com a API aquecida, a resposta a uma pergunta pelo WhatsApp sai em até 15 segundos no p95, contados do recebimento do webhook. |

FR-19 a FR-26 e NFR-17 a NFR-20 são do atendimento humano, seção 29, aprovada na Etapa 17.0 e implementada nas Etapas 17.1 a 17.8.

FR-27 a FR-33 e NFR-21 a NFR-25 são do canal WhatsApp, seção 30, aprovada na Etapa 18.0 e implementada nas Etapas 18.1 a 18.6.

### 5.3 Metas para medir

Estas são metas de aprendizado, não um SLO com acionamento de plantão.

| Sinal | Meta |
|---|---|
| Tempo até o primeiro token em fluxo, API aquecida | p95 abaixo de 3 segundos |
| Resposta pública concluída, API aquecida | p95 abaixo de 12 segundos |
| Ingestão de um documento com menos de 20 páginas | abaixo de 60 segundos |
| Tempo limite do gerador | 120 segundos por chamada e, em seguida, uma nova tentativa em HTTP 429 ou 503. O thinking budget do chat fica em 0. |
| Taxa de respostas `answered` no conjunto de avaliação | pelo menos 90% dos casos que esperam resposta |
| LCP da página inicial, celular médio em 4G | abaixo de 2,5 segundos |
| INP | abaixo de 200 ms |
| CLS | abaixo de 0,1 |
| JavaScript inicial da rota `/`, comprimido | até 200 KB |

A partida a frio de uma réplica Railway adormecida fica de fora das metas de latência.

O JavaScript inicial é tudo o que `/` pede até a rede parar, antes de qualquer interação, somado com gzip. As medidas da Etapa 9.1 e o método estão em [docs/acessibilidade-e-desempenho.md](acessibilidade-e-desempenho.md).


## Mapa da especificação

O documento completo fica dividido por assunto. A numeração das seções não muda, então uma referência como "seção 11.5" continua válida em qualquer arquivo.

| Documento | Seções | Conteúdo |
|---|---|---|
| [Arquitetura, comportamento e dados](sdd/arquitetura.md) | 6 a 8 | Camadas, padrões, fluxos de pergunta, cadastro e ingestão, modelo de dados |
| [Catálogo do corpus](sdd/corpus.md) | 9 | Fatos publicados do hospital fictício |
| [Segurança](sdd/seguranca.md) | 10 | Respostas fixas, limites do modelo, sessão, taxa e segredos |
| [LGPD](sdd/lgpd.md) | 11 | Papéis, bases legais, direitos, retenção e incidentes |
| [API HTTP](sdd/api.md) | 12 | Contrato dos endpoints |
| [Experiência](sdd/experiencia.md) | 13 a 16 | Frontend, design system, plano de UI/UX e GSAP |
| [Provedores e observabilidade](sdd/observabilidade.md) | 17 e 18 | Portas, logs, rastros, métricas e LangSmith |
| [Entrega](sdd/entrega.md) | 19 a 25 | Ambientes, testes, CI/CD, ordem de construção, ADRs e riscos |
| [Atendimento humano](sdd/atendimento-humano.md) | 29 | Oferta, fila, canal em tempo real, dados, segurança e LGPD do atendimento por uma pessoa |
| [Canal WhatsApp](sdd/whatsapp.md) | 30 | Cloud API da Meta, webhook com caixa de entrada e caixa de saída, atendimento pelo WhatsApp, LGPD e custos |

## 26. Decisões em aberto

As decisões D-1 a D-4 fecharam na Etapa 0.1, e as D-5 a D-9, do atendimento humano (seção 29), na Etapa 17.0, em 2026-11-12, todas como a proposta. As decisões D-10 a D-14, do canal WhatsApp (seção 30), fecharam na Etapa 18.0, em 2026-11-12: D-10, D-11, D-13 e D-14 como a proposta, e D-12 alterada.

| ID | Decisão | Onde ficou |
|---|---|---|
| D-1 | Produto em português do Brasil | Seção 2.1 |
| D-2 | LangSmith na região dos Estados Unidos | Seções 2.1, 11.7 e 18.4 |
| D-3 | Dados só fictícios | Seção 2.1 |
| D-4 | Sem domínio próprio | Seção 2.1 |
| D-5 | O atendimento usa SSE e `POST` pelo rewrite de mesma origem, sem WebSocket. A alternativa era WebSocket direto na Railway ou com um domínio próprio. | Seções 29.2 e 29.6, ADR-015 |
| D-6 | O papel `attendant` é separado, e o admin também atende. A alternativa era só o admin atender. | Seções 29.2 e 29.3 |
| D-7 | O texto do atendimento fica 90 dias depois do encerramento, ou menos, com a conversa. A alternativa era 30 dias. | Seções 29.2 e 29.9.9 |
| D-8 | A sessão de `attendant` e de `admin` dura 12 horas. A alternativa era manter os 14 dias. | Seções 29.2 e 29.8 |
| D-9 | O visitante vê só "Equipe do Harborlight", sem o nome de quem atende. A alternativa era o primeiro nome. | Seções 29.2 e 29.9.5 |
| D-10 | Cloud API direta da Meta, sem provedor intermediário. A alternativa é um BSP, como Twilio ou 360dialog, com painel pronto e custo por mensagem. | Seções 30.2 e 30.3, ADR-017 |
| D-11 | O webhook passa pelo rewrite da Vercel, com o segredo da borda e a assinatura da Meta. A alternativa é a rota direto na Railway, isenta do segredo da borda. | Seções 30.3, 30.4 e 30.16 |
| D-12 | Alterada na revisão: o Atrium guarda o BSUID e o número, e só o BSUID é a identidade. O número é reserva de envio. A proposta era não guardar o número; a outra alternativa era guardar só o `wa_id`. | Seções 30.3 e 30.7, ADR-018 |
| D-13 | A conversa do WhatsApp é apagada 30 dias depois da última mensagem da pessoa. A alternativa é 90 dias. | Seções 30.3 e 30.9.7 |
| D-14 | O atendimento pelo WhatsApp usa a mesma fila e o mesmo console da seção 29. A alternativa é só indicar o telefone da mesa. | Seções 30.3 e 30.5 |

## 27. Glossário

| Termo | Significado |
|---|---|
| Chunk | Um pedaço pesquisável de uma versão de documento, com um embedding |
| Versão ativa | A versão do documento cujos chunks podem ser recuperados |
| Piso de similaridade | A similaridade mínima, `RETRIEVAL_MIN_SIMILARITY`, para um chunk entrar no prompt |
| Desfecho (`outcome`) | O resultado gravado de um turno do assistente |
| Porta (`port`) | Um protocolo Python que mantém um provedor substituível |
| Rewrite | A regra da Vercel que encaminha `/backend/*` para a API sem mudar a origem no navegador |
| Política de rastro | O quanto de um passo vai ao LangSmith: tudo, mascarado ou só metadados |
| Titular | A pessoa a quem os dados pessoais se referem |
| Controlador e operador | Quem decide sobre o tratamento e quem trata em nome dele |
| RIPD | Relatório de impacto à proteção de dados pessoais |
| Token de design | Um nome para uma decisão visual, como uma cor ou uma duração |
| Movimento reduzido | O modo em que as animações são trocadas por mudanças diretas |
| Ambiente de development | O ambiente Railway usado pelo laptop e pela primeira etapa do deploy |
| Atendimento humano (`handoff`) | A conversa que passa da IA para uma pessoa da equipe, seção 29 |
| Atendente (`attendant`) | A pessoa da equipe com o papel que só atende, sem acesso ao admin |
| Fila de atendimento | Os atendimentos `queued`, pela ordem do pedido |
| `seq` | O número crescente de cada mensagem de um atendimento, usado para retomar o fluxo |
| `LISTEN/NOTIFY` | O aviso do PostgreSQL entre conexões, entregue só depois do commit |
| Cloud API | A API do WhatsApp Business hospedada pela Meta, seção 30 |
| BSUID | O identificador de uma pessoa do WhatsApp no escopo da empresa, usado no lugar do telefone |
| `wamid` | O id que a Meta dá a cada mensagem do WhatsApp, usado para não processar duas vezes |
| Janela de atendimento | As 24 horas depois da última mensagem da pessoa, em que a empresa responde com texto livre |
| Caixa de entrada e caixa de saída | As tabelas que guardam o evento recebido e a mensagem a enviar antes do trabalho, para nada se perder nem repetir (ADR-017) |

## 28. Histórico de revisão

| Versão | Data | Mudança |
|---|---|---|
| 0.1 | 2026-10-25 | Rascunho inicial a partir das decisões do projeto |
| 0.2 | 2026-10-25 | Especificação traduzida para português |
| 0.3 | 2026-10-25 | Revisão de arquitetura e coerência. Next.js trocado por React com Vite e rewrite da Vercel. Entrega contínua no GitHub Actions. Camada de domínio, unidade de trabalho e padrões explícitos. Railpack no lugar do Nixpacks e semente fora da inicialização. Contrato de embedding de um texto por pedido. Orçamento de tokens, circuit breaker, idempotência e cancelamento. Login limitado, verificação de `Origin` e `no-store`. LangSmith com políticas de rastro, feedback e avaliações. Prometheus, Grafana, painéis e alertas. Seção de LGPD. Design system derivado da imagem de referência. Plano de UI/UX. Movimento com GSAP. ADRs e decisões em aberto. |
| 0.4 | 2026-10-25 | Produto em português. Cadastro e uso só com dados fictícios, mantendo o desenho de LGPD. Sem domínio próprio, com consulta periódica como reserva do fluxo. Especificação dividida por assunto. |
| 1.0 | 2026-10-25 | Revisão final aprovada. Escolhas da seção 2.1 confirmadas. D-2 fechada: LangSmith na região dos Estados Unidos. |
| 1.1 | 2026-10-27 | Contrato da API de conversas: cookie de convidado por 30 dias, 409 com `message_id`, eventos `tick` do diagnóstico, resposta fixa em um `token` e classificação antes da gravação da mensagem. |
| 1.2 | 2026-11-04 | Gestão de documentos do admin: contrato das rotas, ação Tentar de novo com `document.retry`, tipo pela extensão conferido no conteúdo, 409 durante o processamento e ingestão em tarefa de fundo. |
| 1.3 | 2026-11-04 | Visão geral e qualidade do admin: contrato das rotas, `messages.request_id`, `LANGSMITH_RUN_URL_TEMPLATE`, intenção derivada do desfecho e funil pela validade da sessão. |
| 1.4 | 2026-11-06 | Fila de pedidos de titular do admin: contrato das rotas, fechamento só com nota de resolução, pedido fechado imutável, motivo de `dsr.update` sem conteúdo e `DueDateBadge` com prazo próximo em 3 dias. |
| 1.5 | 2026-11-06 | Publicação: serviços da Railway configurados pela API (ADR-013), API pelo Dockerfile em `0.0.0.0`, semente adiada sem a chave, provedores indisponíveis sem `GEMINI_API_KEY`, `deploy.yml` com `DEPLOY_ENABLED`, alias estável do preview, fumaça em script, adaptador `demo` e e2e com a API real (ADR-014), e CSP com `style-src` para o Radix. |
| 1.6 | 2026-11-06 | Acabamento: alvos de toque com as exceções do WCAG 2.5.8, nome acessível com o texto visível, rótulos em `sr-only` sem `visibility: hidden`, menu do visitante como disclosure, foco da troca de rota que respeita quem já está na página, rotas de `/` como `modulepreload`, barra lateral e paleta sob demanda, barra do topo reservada no celular e auditoria, teclado e desempenho na suíte ao vivo. |
| 1.7 | 2026-11-06 | Teste de usabilidade: tarefas por persona de visitante, dados fictícios e roteiro, registro e resultados em `docs/usabilidade/`. |
| 1.8 | 2026-11-06 | Produção e rollback: Environments `development` e `production` só na `main`, com revisor obrigatório em `production`, serviços da Railway presos a um commit, `/health` com o commit da Railway sem o `BUILD_SHA` e roteiro de rollback testado em `docs/rollback.md`. |
| 1.9 | 2026-11-06 | M13 com o Flip: a largura da barra lateral troca direto, os ícones se movem só com `transform`, casados pelo `data-flip-id`, e o Flip é registrado em `src/motion/flip.ts`, fora do JavaScript inicial de `/`. |
| 1.10 | 2026-11-07 | Teto diário de tokens registrado na seção 22.1: `500000` em development e `2000000` em production. |
| 1.11 | 2026-11-07 | Ordem de construção com o passo 11, das melhorias da auditoria: Fases 11 a 16 do plano de ação. |
| 1.12 | 2026-11-07 | CI que não passa vazia: `REQUIRE_INTEGRATION_DB=1` no job `api` troca o pulo da integração por falha, e o Vitest roda nos projetos `dom` e `node` (seção 21.1). |
| 1.13 | 2026-11-07 | Alertas no Discord: o contato `atrium-operacao` posta no webhook de `DISCORD_WEBHOOK_URL`, porque a Railway só libera SMTP no plano Pro (seção 18.3). |
| 1.14 | 2026-11-07 | Ordem de construção: rollback conferido, CI endurecida e cobertura medida ficam como débito técnico, e o custo do LLM entra antes deles (seção 23). |
| 1.15 | 2026-11-07 | Orçamento obrigatório: em `development` e `production`, a API não sobe com `LLM_DAILY_TOKEN_BUDGET` menor ou igual a zero nem com `RATE_LIMIT_HMAC_KEY` ou `PSEUDONYM_KEY` vazias, conferido em `create_app` (seções 7.1, 10.4, 19 e 22.1). |
| 1.16 | 2026-11-07 | Todo token entra no orçamento: o cadastro por chat consulta o teto antes de cada turno e grava os tokens depois, e uma resposta cancelada grava o uso parcial que o adaptador já contou (seções 6.4, 7.1 e 7.2). |
| 1.17 | 2026-11-07 | Histórico com janela: reescrita e geração recebem as últimas 6 trocas, até 6.000 caracteres, começando por uma pergunta do visitante (seção 7.1). |
| 1.18 | 2026-11-07 | Vida de processo: o `AiRuntime`, com o provedor de chat, o circuit breaker e os workflows, nasce no `lifespan`, e a API abre um engine com pool para as sessões dos pedidos (seções 6.2, 6.4 e 7.1). |
| 1.19 | 2026-11-07 | Segredo da borda: a rota de `/backend` da Vercel manda `x-atrium-edge` com o `EDGE_SECRET` do ambiente, e a API recusa `/v1` sem ele em development e production. O `vercel.ts` passa a declarar só `routes` (seções 10.3, 10.4, 10.6, 17, 19, 21.1, 22.1 e 22.2, ADR-001). |
| 1.20 | 2026-11-07 | Segredo da borda obrigatório: em development e production, a API não sobe sem `EDGE_SECRET`, e a fumaça confere o 403 de `/v1` e o 200 de `/health` direto na Railway (seções 7.1, 10.3, 19, 21.1 e 22.3). |
| 1.21 | 2026-11-08 | Documentação, sem mudança de comportamento: disposição do repositório com as pastas atuais e os READMEs de pasta (seção 6.3), Docker Compose como alternativa opcional e não requisito (seção 4.2), API construída pelo Dockerfile (seção 6.1), API em `0.0.0.0` (seção 18.3), testes do frontend sem MSW e Playwright simulado no job `web` (seções 21.1 e 22.3), tabelas, paleta e avisos sem TanStack Table, `cmdk` e Sonner (seção 13.1), `vercel.ts` descrito pelas rotas (seção 13.4), `PSEUDONYM_KEY` entre os segredos (seção 10.6), nome do repositório, mapa da documentação em `docs/README.md` e guia do código em `docs/guia/`. |
| 1.23 | 2026-11-10 | Proposta do atendimento humano, em revisão na Etapa 17.0: seção 29, FR-19 a FR-26, NFR-17 a NFR-20, decisões D-5 a D-9, ADR-015 (SSE e `POST` pelo rewrite em vez de WebSocket), ADR-016 (`LISTEN/NOTIFY`), passo 12 da ordem de construção e Fase 17 do plano de ação. Nenhum comportamento existente muda até a aprovação. |
| 1.24 | 2026-11-12 | Atendimento humano aprovado na Etapa 17.0: D-5 a D-9 fechadas como a proposta, seção 29, ADR-015 e ADR-016 sem o status de proposta, e ponteiros para a seção 29 nas seções 8.1, 10, 11, 12, 15.3, 15.4 e 18.3. |
| 1.25 | 2026-11-12 | Conversa do membro só para o membro (Etapa 15.1): o cadastro zera o `guest_key_id` das conversas anexadas, a chave de convidado só abre conversa sem membro, o `atrium_guest` sai no login, no fim do cadastro e no logout, e quem não é dono recebe 404 nas rotas de conversa (seções 7.2, 10.3 e 12). |
| 1.26 | 2026-11-12 | Atendimento humano implementado nas Etapas 17.1 a 17.7, em revisão: domínio, migração `0010_handoffs`, papel `attendant` e sessão de 12 horas, `LISTEN/NOTIFY`, fluxos SSE com retomada, rotas do visitante, da equipe e do admin, telas da conversa, do console e dos encerrados. Na seção 29.11, o motivo da capacidade aparece em texto, a categoria da remoção usa um `ToggleGroup` de escolha única e o som opcional fica para depois. Na seção 29.14, o `docker-compose.yml` liga o serviço e cria as contas de teste. Os scripts `attendants` e `attendance_dev` entram na seção 6.3. |
| 1.27 | 2026-11-12 | Proposta do canal WhatsApp, em revisão na Etapa 18.0: seção 30, FR-27 a FR-33, NFR-21 a NFR-25, decisões D-10 a D-14, ADR-017 (Cloud API com caixa de entrada e caixa de saída no PostgreSQL), ADR-018 (identidade pelo BSUID), passo 13 da ordem de construção e Fase 18 do plano de ação. Nenhum comportamento existente muda até a aprovação. |
| 1.28 | 2026-11-12 | Canal WhatsApp aprovado na Etapa 18.0 e implementado nas Etapas 18.1 a 18.6, em revisão: D-10, D-11, D-13 e D-14 como a proposta, D-12 alterada (BSUID como identidade e o número como reserva de envio), ADR-017 e ADR-018 aceitos, migração `0011_whatsapp` com a chave de convidado interna do contato, repasse do atendimento por cursor, webhook com 422 para corpo grande, painel e alertas do canal, seção WhatsApp no Aviso de Privacidade e `LEGAL_DOCUMENT_VERSION` 2026-11-12.1 (seções 11, 18.3 e 30). |
| 1.29 | 2026-11-13 | Canal WhatsApp: o número de teste americano da Meta não envia para números brasileiros (erro 130497), então development usa um número brasileiro de estudo. O console mostra um motivo próprio para o 130497 (seção 30). |
