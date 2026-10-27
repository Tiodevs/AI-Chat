# Documento de especificação de software — Atrium

| | |
|---|---|
| Produto | Atrium, assistente público para visitantes do Harborlight General Hospital |
| Repositório | IA-Chat |
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
| Modelo de chat | `gemini-3.8-flash`, substituível por `CHAT_MODEL` |
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
| Nome do produto **Atrium**. Hospital **Harborlight General Hospital**, na cidade fictícia de **Port Meridian**. | O repositório pode continuar `IA-Chat`. O produto precisa de um nome estável para prompts, documentos e interface. |
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

### 4.2 Fora do escopo

Prontuário eletrônico, HL7, FHIR, elegibilidade de convênio, marcação de consulta, pagamentos, SMS, entrega de e-mail, recuperação de senha, interface em vários idiomas, tema claro, aplicativos móveis nativos, busca de políticas só para a equipe, banco vetorial separado, Kubernetes, pilha local de Docker Compose, renderização no servidor e plantão com pager.

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

### 5.3 Metas para medir

Estas são metas de aprendizado, não um SLO com acionamento de plantão.

| Sinal | Meta |
|---|---|
| Tempo até o primeiro token em fluxo, API aquecida | p95 abaixo de 3 segundos |
| Resposta pública concluída, API aquecida | p95 abaixo de 12 segundos |
| Ingestão de um documento com menos de 20 páginas | abaixo de 60 segundos |
| Tempo limite do gerador | 40 segundos por chamada e, em seguida, uma nova tentativa em HTTP 429 ou 503 |
| Taxa de respostas `answered` no conjunto de avaliação | pelo menos 90% dos casos que esperam resposta |
| LCP da página inicial, celular médio em 4G | abaixo de 2,5 segundos |
| INP | abaixo de 200 ms |
| CLS | abaixo de 0,1 |
| JavaScript inicial da rota `/`, comprimido | até 200 KB |

A partida a frio de uma réplica Railway adormecida fica de fora das metas de latência.


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

## 26. Decisões em aberto

Não há decisões em aberto. Nenhuma decisão bloqueia as Etapas 1 a 4.

| ID | Decisão | Onde ficou |
|---|---|---|
| D-1 | Produto em português do Brasil | Seção 2.1 |
| D-2 | LangSmith na região dos Estados Unidos | Seções 2.1, 11.7 e 18.4 |
| D-3 | Dados só fictícios | Seção 2.1 |
| D-4 | Sem domínio próprio | Seção 2.1 |

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

## 28. Histórico de revisão

| Versão | Data | Mudança |
|---|---|---|
| 0.1 | 2026-10-25 | Rascunho inicial a partir das decisões do projeto |
| 0.2 | 2026-10-25 | Especificação traduzida para português |
| 0.3 | 2026-10-25 | Revisão de arquitetura e coerência. Next.js trocado por React com Vite e rewrite da Vercel. Entrega contínua no GitHub Actions. Camada de domínio, unidade de trabalho e padrões explícitos. Railpack no lugar do Nixpacks e semente fora da inicialização. Contrato de embedding de um texto por pedido. Orçamento de tokens, circuit breaker, idempotência e cancelamento. Login limitado, verificação de `Origin` e `no-store`. LangSmith com políticas de rastro, feedback e avaliações. Prometheus, Grafana, painéis e alertas. Seção de LGPD. Design system derivado da imagem de referência. Plano de UI/UX. Movimento com GSAP. ADRs e decisões em aberto. |
| 0.4 | 2026-10-25 | Produto em português. Cadastro e uso só com dados fictícios, mantendo o desenho de LGPD. Sem domínio próprio, com consulta periódica como reserva do fluxo. Especificação dividida por assunto. |
| 1.0 | 2026-10-25 | Revisão final aprovada. Escolhas da seção 2.1 confirmadas. D-2 fechada: LangSmith na região dos Estados Unidos. |
