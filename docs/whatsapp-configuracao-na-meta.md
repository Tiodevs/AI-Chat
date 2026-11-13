# Configuração do canal WhatsApp na Meta

Passo a passo do que precisa ser criado fora do repositório para o canal WhatsApp da seção 30 do SDD funcionar. A ordem segue as etapas da Fase 18 do plano de ação. O que é segredo vai só para as variáveis do serviço `api` da Railway, nunca para o repositório nem para o chat.

Os nomes dos menus da Meta mudam com frequência. Quando um botão não estiver onde o texto diz, procure pelo nome em inglês entre parênteses.

## Visão geral

| Item | Para quê | Variável | Etapa |
|---|---|---|---|
| Conta de desenvolvedor da Meta | Criar o app | — | 18.0 |
| Portfólio empresarial | Dono do app, do número e do usuário do sistema | — | 18.0 |
| App do tipo Business com o WhatsApp | Recebe o webhook e dá o número de teste | — | 18.0 |
| Id do número de telefone | De qual número a API envia | `WHATSAPP_PHONE_NUMBER_ID` | 18.0 |
| Id da conta do WhatsApp Business | Conta dona do número | `WHATSAPP_BUSINESS_ACCOUNT_ID` | 18.0 |
| Chave secreta do app | Conferir a assinatura do webhook | `WHATSAPP_APP_SECRET` | 18.2 |
| Token de verificação | Responder à verificação do webhook | `WHATSAPP_VERIFY_TOKEN` | 18.2 |
| Token permanente do usuário do sistema | Enviar mensagens pela Graph API | `WHATSAPP_ACCESS_TOKEN` | 18.2 |
| Webhook apontado para a Vercel | A Meta entregar as mensagens | — | 18.2 |
| Forma de pagamento | Passar da cota grátis de 1.000 mensagens de serviço por mês | — | 18.6 |
| Número próprio | Produção | — | 18.6 |

## 1. Conta de desenvolvedor

1. Abra [developers.facebook.com](https://developers.facebook.com) e entre com a sua conta do Facebook.
2. Clique em **Começar** (Get Started) e confirme o telefone e o e-mail que a Meta pedir.
3. Escolha a função **Desenvolvedor** e conclua.

## 2. Portfólio empresarial

1. Abra [business.facebook.com](https://business.facebook.com) e crie um portfólio (Business portfolio).
2. Use o nome do seu negócio. Para estudo não precisa verificar o negócio. A verificação só é necessária para o número próprio e para limites maiores (Etapa 18.6).
3. O hospital é fictício: não use o nome Harborlight num portfólio verificado nem num nome de exibição de produção. No número de teste, o nome que aparece é o da Meta.

## 3. App com o WhatsApp

1. Em [developers.facebook.com/apps](https://developers.facebook.com/apps), clique em **Criar app** (Create app).
2. No caso de uso, escolha **Conectar-se com clientes pelo WhatsApp** (Connect with customers through WhatsApp). Se pedir o tipo, escolha **Empresa** (Business).
3. Dê o nome `atrium-dev` e ligue o app ao portfólio do passo 2.
4. No painel do app, abra **WhatsApp → Configuração da API** (API Setup). A Meta cria uma conta do WhatsApp Business de teste e um **número de teste**, grátis.
5. Copie para um lugar seguro:
   - **Identificação do número de telefone** (Phone number ID): vai em `WHATSAPP_PHONE_NUMBER_ID`.
   - **Identificação da conta do WhatsApp Business** (WhatsApp Business Account ID): vai em `WHATSAPP_BUSINESS_ACCOUNT_ID`.
6. Em **Para** (To), clique em **Gerenciar lista de números** e adicione o seu WhatsApp. A Meta manda um código para ele. O número de teste só conversa com até 5 números cadastrados assim.
7. Ainda na mesma tela, clique em **Enviar mensagem** com o modelo `hello_world`. Se ela chegar no seu celular, o app está funcionando. Esse é o teste da Etapa 18.0.
8. Responda qualquer coisa a essa mensagem no celular. Isso abre a janela de 24 horas em que o Atrium pode responder com texto livre.

## 4. Chave secreta do app

1. No painel do app, abra **Configurações do app → Básico** (App settings → Basic).
2. Em **Chave secreta do app** (App secret), clique em **Mostrar** e confirme a senha.
3. O valor vai em `WHATSAPP_APP_SECRET`. É ele que assina cada webhook com `X-Hub-Signature-256`.

## 5. Token de verificação

É um valor que você inventa. A Meta o manda de volta na hora de verificar o webhook, e a API compara. Gere um valor aleatório para cada ambiente:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

O valor vai em `WHATSAPP_VERIFY_TOKEN`, e o mesmo valor é digitado no painel da Meta no passo 8.

## 6. Usuário do sistema e token permanente

O token da tela de Configuração da API vence em 24 horas. A API usa o token de um usuário do sistema, que não vence.

1. Em [business.facebook.com](https://business.facebook.com), abra **Configurações → Usuários → Usuários do sistema** (Settings → Users → System users).
2. Clique em **Adicionar**, dê o nome `atrium-api` e a função **Funcionário** (Employee).
3. Clique em **Atribuir ativos** (Assign assets):
   - em **Apps**, escolha `atrium-dev` com controle total;
   - em **Contas do WhatsApp**, escolha a conta de teste com controle total.
4. Clique em **Gerar token** (Generate token), escolha o app `atrium-dev`, a validade **Nunca** e só estas duas permissões:
   - `whatsapp_business_messaging`
   - `whatsapp_business_management`
5. Copie o token na hora, porque a Meta não mostra de novo. Ele vai em `WHATSAPP_ACCESS_TOKEN`.

## 7. Variáveis na Railway

No projeto da Railway, ambiente `development`, serviço `api`, aba **Variables**:

| Variável | Valor |
|---|---|
| `WHATSAPP_ENABLED` | `false` por enquanto |
| `WHATSAPP_PHONE_NUMBER_ID` | Do passo 3 |
| `WHATSAPP_BUSINESS_ACCOUNT_ID` | Do passo 3 |
| `WHATSAPP_APP_SECRET` | Do passo 4 |
| `WHATSAPP_VERIFY_TOKEN` | Do passo 5 |
| `WHATSAPP_ACCESS_TOKEN` | Do passo 6 |

Gravar uma variável na Railway republica o serviço com o commit do topo da `main`, sem passar pela aprovação do pipeline. Grave com `WHATSAPP_ENABLED=false`: com o canal desligado, a API ignora as outras e sobe normalmente.

`WHATSAPP_GRAPH_VERSION` não precisa ser gravada. O padrão fica no código e muda por PR.

## 8. Webhook

Só funciona depois que o código da Fase 18 estiver publicado em development e `WHATSAPP_ENABLED` estiver `true` lá, porque a rota só existe com o canal ligado.

1. No painel do app, abra **WhatsApp → Configuração** (Configuration).
2. Em **Webhook**, clique em **Editar**:
   - **URL de callback**: `https://<url da Vercel de development>/backend/v1/whatsapp/webhook`
   - **Token de verificação**: o valor de `WHATSAPP_VERIFY_TOKEN` de development
3. Clique em **Verificar e salvar**. A Meta chama o `GET` da rota, e a API devolve o desafio.
4. Em **Campos do webhook** (Webhook fields), assine **messages**. É esse campo que traz as mensagens recebidas e os status de entrega.
5. Mande uma mensagem do seu celular para o número de teste. A resposta do Atrium chega em alguns segundos.

Se a verificação falhar, confira três coisas: o caminho termina em `/backend/v1/whatsapp/webhook`, o token é o mesmo nos dois lados, e o deploy com `WHATSAPP_ENABLED=true` terminou.

Se a verificação passar e as mensagens não chegarem, a Meta pode estar segurando os webhooks porque o app está em modo de desenvolvimento. Publique o app em **Publicar** (Publish). A Meta pede a URL da política de privacidade: use `https://<url da Vercel>/privacy`.

## 9. Testar na sua máquina, sem publicar

Para ver o webhook chegando na API local antes de publicar:

1. Suba a API com `uv run uvicorn app.main:app --reload` e, no `apps/api/.env`, `WHATSAPP_ENABLED=true` e as variáveis do passo 7.
2. Abra um túnel HTTPS para a porta 8000 com uma ferramenta de túnel, como o `cloudflared tunnel --url http://localhost:8000`.
3. Aponte o webhook do passo 8 para `https://<endereço do túnel>/v1/whatsapp/webhook`. Localmente não há `/backend`, porque não há Vercel, e o segredo da borda fica desligado.
4. Volte o webhook para a Vercel de development quando terminar.

## 10. Produção (Etapa 18.6)

1. **Número próprio.** Um chip que receba SMS ou ligação e que não esteja em uso no aplicativo do WhatsApp. Se estiver, apague a conta do WhatsApp nesse número antes.
2. No [Gerenciador do WhatsApp](https://business.facebook.com/wa/manage/phone-numbers/) (WhatsApp Manager), clique em **Adicionar número**, confirme pelo código e escolha um **nome de exibição** ligado ao seu negócio. A Meta aprova o nome.
3. Crie um PIN de duas etapas para o número quando a Meta pedir.
4. **Forma de pagamento.** Em **Configurações de pagamento** do WhatsApp, cadastre um cartão. Prefira a cobrança em reais, faturada pela Facebook Brasil. Sem forma de pagamento, a Meta para as mensagens de serviço depois das 1.000 grátis do mês.
5. Repita os passos 4 a 8 para o ambiente `production`, com um token de verificação próprio e o webhook apontado para a Vercel de production. O segredo e o token podem ser de um app separado, `atrium-prod`, o que é recomendado.
6. Ligue `WHATSAPP_ENABLED=true` em production só depois da sua aprovação na Etapa 18.6.

## Ferramentas opcionais

- **WhatsApp Business Tools MCP**, servidor oficial da Meta, em fase inicial. Cria a conta, registra número, configura webhook e manda mensagem de teste pelo Claude Code. É para desenvolvimento, não para envio em produção.

  ```bash
  claude mcp add --transport http whatsapp_business_tools https://mcp.facebook.com/whatsapp_business_tools
  ```

  Depois rode `/mcp` no Claude Code e entre com a conta da Meta.
- Evite servidores MCP não oficiais que controlam o WhatsApp Web: eles podem levar ao banimento do número.

## Rotação do token

1. Gere um token novo no usuário do sistema (passo 6).
2. Grave em `WHATSAPP_ACCESS_TOKEN` na Railway e espere o deploy.
3. Em **Usuários do sistema**, revogue o token antigo.
4. Mande uma mensagem de teste e confira o alerta "Envio falhando" sem disparar.
