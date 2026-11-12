# Segurança

Parte da [especificação do Atrium](../sdd.md). A numeração das seções é a do documento completo.

## 10. Segurança

O atendimento humano acrescenta as ameaças, os controles, os limites de taxa e a sessão de 12 horas da equipe da seção 29.8.

### 10.1 Respostas fixas

Os textos abaixo são a cópia em português que o produto mostra.

**Orientação médica.** "Não posso ajudar com sintomas, diagnóstico ou medicamento. Se for uma emergência, ligue para o número local de emergência. A entrada de emergência do Harborlight fica no lado oeste e funciona 24 horas. Para outras perguntas sobre o hospital, ligue (555) 014-2600."

**Fora de tema.** "Posso responder perguntas sobre como visitar e usar o Harborlight General Hospital."

**Abstenção e falha de fundamentação.** "Não encontrei isso nas informações publicadas do Harborlight. Você pode ligar para a mesa telefônica no (555) 014-2600."

**Indisponibilidade.** "O Atrium está temporariamente indisponível. Você pode ligar para a mesa telefônica no (555) 014-2600."

Esses quatro textos ficam em `app/prompts/qa.py`. `domain/outcomes.py` escolhe o desfecho, e o texto vem do prompt. Abstenção e falha de fundamentação compartilham o mesmo texto. O desfecho `error` reutiliza o texto de indisponibilidade.

A interface mostra um aviso permanente: o Atrium é uma IA, responde a partir da informação publicada do hospital e não dá orientação médica.

### 10.2 Limites do modelo

- A instrução de sistema, escrita em português, diz que o modelo responde em português, só a partir do contexto numerado, cita esses números e ignora instruções encontradas dentro de um documento ou de uma mensagem do visitante.
- Cada bloco de contexto é delimitado e rotulado como não confiável.
- Só um admin pode mudar o corpus. O texto do documento continua delimitado, porque um arquivo enviado pode conter instruções.
- O schema da ferramenta de cadastro é a lista de permissão. `role`, consentimentos e `password` não são campos da ferramenta.
- A temperatura da extração e da classificação é 0. A temperatura da resposta ao visitante é 0,2.
- Cada prompt tem uma constante `PROMPT_VERSION`, por exemplo `qa-generate@2026-10-25.1`. Mudar o texto exige mudar a versão. Um teste falha se o hash do texto mudar sem a versão mudar.

### 10.3 Sessão e transporte

- O cookie de sessão é `atrium_session`. O de convidado é `atrium_guest`. Os dois são `HttpOnly`, `SameSite=Lax`, sem atributo `Domain`, e `Secure` fora do ambiente local. O cookie `atrium_guest` dura 30 dias, o mesmo prazo de retenção das conversas de convidado, e é apagado no login, no fim do cadastro e no logout. A chave de convidado só abre uma conversa sem membro, e quem não é dono de uma conversa recebe o mesmo 404 de uma conversa inexistente.
- O navegador guarda os cookies na origem do frontend porque o rewrite é de mesma origem.
- A sessão de autenticação dura 14 dias. As sessões de cadastro expiram em 24 horas.
- Sair revoga a sessão.
- Pedidos com método `POST`, `PUT`, `PATCH` ou `DELETE` precisam de `Origin` igual a `WEB_ORIGIN`. Isso complementa o `SameSite=Lax` contra CSRF.
- A API não usa o cabeçalho `Authorization` para identificar usuários. Ele só vale para `/metrics`.
- Toda resposta de `/v1` sai com `Cache-Control: no-store`. A Vercel também recebe `x-vercel-enable-rewrite-caching: 0` em `/backend/*`, porque projetos novos podem armazenar em cache respostas de rewrites externos.
- O Uvicorn roda com `--proxy-headers`. O IP do cliente vem do primeiro item de `x-forwarded-for` e é usado só para o HMAC do limite de taxa.
- **Segredo da borda.** A Vercel sobrescreve o `x-forwarded-for` com o IP de quem a chamou e, na rota de `/backend`, põe o cabeçalho `x-atrium-edge` com o `EDGE_SECRET` do ambiente, trocando qualquer valor que o visitante mande. Em `development` e `production`, a API responde 403 (`forbidden`) a um pedido a `/v1` sem esse cabeçalho ou com outro valor, comparado em tempo constante, e não sobe sem `EDGE_SECRET` (seção 7.1). Assim o primeiro item do `x-forwarded-for` de um pedido a `/v1` vem sempre da Vercel. `/health`, `/ready` e `/metrics` ficam fora, para a Railway e o Prometheus, que chamam a API direto. Em `local` e `test`, o Vite faz o proxy sem o cabeçalho, e a API não o exige. Na primeira publicação, a Vercel passou a mandar o cabeçalho antes de a Railway receber o segredo, para nenhum pedido do app cair no 403. A fumaça da seção 22.3 confere o 403 direto na Railway.
- O CORS permite só `WEB_ORIGIN`. O tráfego normal não precisa de CORS.

### 10.4 Limites de taxa

Janelas fixas gravadas em `rate_limit_windows`.

| Balde | Limite |
|---|---|
| Login por e-mail | 10 tentativas a cada 15 minutos |
| Login por IP | 30 por hora |
| Mensagens de cadastro, senha e envio do formulário, por IP | 20 por hora |
| Perguntas de convidado, por chave de convidado | 30 por hora |
| Perguntas de convidado, por IP | 60 por hora |
| Perguntas de membro, por usuário | 120 por hora |
| Diagnóstico de fluxo, por IP | 60 por hora |
| Pedidos de titular, por IP | 5 por dia |
| Uploads de admin, por admin | 30 por hora |

Um pedido limitado devolve HTTP 429 com `retry_after_seconds`. Um erro de login nunca diz se o e-mail existe.

A API da Railway é pública, e `x-forwarded-for` pode ser forjado por quem a chama diretamente. Com o segredo da borda (seção 10.3), esse pedido recebe 403 em `/v1`, e o IP dos limites passa a vir da Vercel. Os limites por IP continuam sendo de melhor esforço, porque um IP não identifica uma pessoa. A proteção de custo que não pode ser contornada é o orçamento diário de tokens da seção 7.1, e por isso a API não sobe em `development` nem em `production` com ele desligado.

### 10.5 Contas de admin

`python -m app.scripts.bootstrap_admin` roda no pré-deploy. Se nenhum usuário tem `role = admin`, ele cria um a partir de `ADMIN_EMAIL` e `ADMIN_PASSWORD`. Quando um admin já existe, essas variáveis são ignoradas. O serviço público de cadastro fixa `role = member` no código. Um admin não pode excluir a própria conta pela API. A remoção é feita com `railway run python -m app.scripts.bootstrap_admin --remove <email>`, que recusa remover o último admin.

### 10.6 Segredos

`.env.example` lista as chaves e não contém segredo real. `GEMINI_API_KEY`, `LANGSMITH_API_KEY`, `ADMIN_PASSWORD`, `METRICS_TOKEN`, `RATE_LIMIT_HMAC_KEY`, `PSEUDONYM_KEY`, `EDGE_SECRET` e as senhas de banco são variáveis de ambiente. Elas estão ausentes de rastros, logs e exemplos do OpenAPI. Os segredos de implantação do GitHub ficam em GitHub Environments, separados por ambiente.

