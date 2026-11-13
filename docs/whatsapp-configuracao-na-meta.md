# Configuração do canal WhatsApp na Meta

Passo a passo do que precisa ser criado fora do repositório para o canal WhatsApp da seção 30 do SDD funcionar. A ordem segue as etapas da Fase 18 do plano de ação. O que é segredo vai só para as variáveis do serviço `api` da Railway, nunca para o repositório nem para o chat.

Os nomes dos menus da Meta mudam com frequência. Os deste guia foram conferidos em 13 de novembro de 2026, no painel novo, organizado por casos de uso. Quando um botão não estiver onde o texto diz, procure pelo nome em inglês entre parênteses.

> [!IMPORTANT]
> O número de teste que a Meta dá é americano (+1 555) e **não envia para números brasileiros**: todo envio volta com o erro 130497. Para testar o Atrium no Brasil, você precisa de um número brasileiro na conta, como explica o passo 4. Para estudo, um eSIM pré-pago resolve.

## Visão geral

| Item | Para quê | Variável | Etapa |
|---|---|---|---|
| Conta de desenvolvedor da Meta | Criar o app | — | 18.0 |
| Portfólio empresarial | Dono do app, do número e do usuário do sistema | — | 18.0 |
| App com o caso de uso do WhatsApp | Recebe o webhook e dá o número de teste | — | 18.0 |
| Número brasileiro (eSIM pré-pago) | Enviar para números do Brasil | — | 18.0 |
| Identificação do número de telefone | De qual número a API envia | `WHATSAPP_PHONE_NUMBER_ID` | 18.0 |
| Identificação da conta do WhatsApp Business | Conta dona do número | `WHATSAPP_BUSINESS_ACCOUNT_ID` | 18.0 |
| Chave secreta do app | Conferir a assinatura do webhook | `WHATSAPP_APP_SECRET` | 18.2 |
| Token de verificação | Responder à verificação do webhook | `WHATSAPP_VERIFY_TOKEN` | 18.2 |
| Token permanente do usuário do sistema | Enviar mensagens pela Graph API | `WHATSAPP_ACCESS_TOKEN` | 18.2 |
| Webhook apontado para a Vercel | A Meta entregar as mensagens | — | 18.2 |
| Forma de pagamento | Registrar o número e passar da cota grátis de 1.000 mensagens de serviço por mês | — | 18.0 e 18.6 |

## 1. Conta de desenvolvedor

1. Abra [developers.facebook.com](https://developers.facebook.com) e entre com a sua conta do Facebook.
2. Clique em **Começar** (Get Started) e confirme o telefone e o e-mail que a Meta pedir.
3. Escolha a função **Desenvolvedor** e conclua.

## 2. Portfólio empresarial

1. Abra [business.facebook.com](https://business.facebook.com) e crie um portfólio (Business portfolio).
2. Use o nome do seu negócio e o país **Brasil**. Para estudo não precisa verificar o negócio.
3. O hospital é fictício: não use o nome Harborlight no portfólio nem no nome de exibição do número.

## 3. App e número de teste

1. Em [developers.facebook.com/apps](https://developers.facebook.com/apps), clique em **Criar app** (Create app).
2. No caso de uso, escolha **Conectar-se com clientes pelo WhatsApp** (Connect with customers through WhatsApp). Se pedir o tipo, escolha **Empresa** (Business).
3. Dê o nome `atrium-dev` e ligue o app ao portfólio do passo 2.
4. No **Painel** do app, clique em **Personalizar o caso de uso "Conectar-se com os clientes pelo WhatsApp"**. O mesmo lugar abre por **Casos de uso → Personalizar**, no menu da esquerda.
5. Abra **Configuração básica → Etapa 1. Experimente** (Quickstart). É a antiga Configuração da API (API Setup). Em **Reivindicar um número de teste do WhatsApp**, a Meta cria uma conta de teste e um número americano, grátis.
6. Anote os dois ids que a tela mostra. Eles não são segredo:
   - **Phone Number ID**: identifica o número.
   - **Identificação da conta de mensagens**: é o WhatsApp Business Account ID.

   Esses ids são do número de teste. O Atrium vai usar os do número brasileiro, do passo 4.
7. Em **Envie uma mensagem do seu número de teste**, cadastre o seu WhatsApp em **Destinatário** e confirme pelo código que chega nele. O número de teste só conversa com até 5 números cadastrados assim.
8. Clique em **Enviar mensagem**. Para um número brasileiro, o `hello_world` **não chega**. Em **Verifique webhooks de teste**, abra o payload e veja `"status": "failed"` com `"code": 130497`. Isso é esperado e confirma que o app está ligado.
9. Do seu celular, mande "oi" para o número de teste. Um evento novo com `messages` aparece na mesma tabela. Ele mostra o formato que o Atrium recebe: o BSUID em `from_user_id`, como `BR.1145...`, e o `wa_id` exatamente como a Meta guarda o seu número.

O número de teste serve para isso: ver o formato dos webhooks. Para conversar de verdade no Brasil, siga o passo 4.

### Por que o número de teste não envia para o Brasil

A Meta restringe o envio entre países para destinatários no Brasil e na Indonésia quando a empresa ainda não tem reputação de envio. A restrição vale também para a resposta dentro da janela de 24 horas, testada em 12 de novembro de 2026. Ela só cai quando a conta chega ao nível de 2.000 conversas e se mantém assim por um tempo. Com um número brasileiro, o envio deixa de ser entre países e a restrição não se aplica.

## 4. Número brasileiro para estudo

Para estudo, o jeito mais barato e rápido é um **eSIM pré-pago** de uma operadora brasileira, como segunda linha no celular. O iPhone 15 vendido no Brasil aceita um chip físico e eSIMs ao mesmo tempo, então a sua linha principal continua como está.

### O que serve e o que não serve

| Opção | Serve? | Por quê |
|---|---|---|
| eSIM pré-pago de Vivo, Claro ou TIM | Sim, a mais simples | Em seu CPF, ativa em minutos e custa basicamente a menor recarga |
| Chip físico pré-pago | Sim | Mesmo custo. Use se a operadora não ativar eSIM pré-pago pelo app |
| Um telefone fixo seu que não esteja no WhatsApp | Sim, e de graça | A Meta confirma por ligação de voz |
| O seu número pessoal | Não | Ele sairia do aplicativo do WhatsApp: um número fica ou no app ou na API, nunca nos dois |
| Sites de "número virtual" ou de receber SMS | Não | Números compartilhados, muitas vezes já bloqueados pela Meta. Outra pessoa pode registrar o número depois |

### Passo a passo com o eSIM

1. **Escolha a operadora** com melhor sinal onde você está. No app ou no site da operadora, procure **eSIM pré-pago** (ou "chip virtual"). Algumas pedem para ativar primeiro um chip físico e migrar para eSIM depois. Nesse caso, compre o chip físico, que tem o mesmo custo.
2. **Faça o cadastro com o seu CPF**, como exige a Anatel, e escolha a **menor recarga**. Para receber o SMS da Meta não precisa de plano de dados. Confira o preço no app da operadora, porque muda com frequência.
3. **Instale o eSIM no iPhone**: Ajustes → Celular → **Adicionar eSIM**, e leia o QR code ou use a ativação pelo app. Quando o iPhone perguntar, deixe a linha principal para dados, iMessage e FaceTime, e dê ao eSIM um nome como "Atrium".
4. **Não instale o WhatsApp nesse número.** O WhatsApp do seu iPhone continua no número pessoal. A linha nova só precisa receber o SMS, ou a ligação, de confirmação da Meta.
5. **Adicione o número na Meta.** No painel do app, abra **Configuração básica → Etapa 2. Configuração de produção** e procure **Adicionar número de telefone** (Add phone number). O mesmo botão existe no [Gerenciador do WhatsApp](https://business.facebook.com/wa/manage/phone-numbers/) (WhatsApp Manager).
   - **Nome de exibição**: um nome ligado ao seu portfólio, como "Atrium Estudo". A Meta revisa o nome. Enquanto a revisão não termina, a pessoa vê o número no lugar do nome.
   - **Categoria**: Educação ou Outro.
   - **Número**: `+55`, DDD e o número do eSIM, com o 9.
   - **Confirmação**: escolha SMS, ou ligação se o SMS não chegar, e digite o código.
6. **Forma de pagamento.** Se a Meta pedir para registrar o número, cadastre um cartão em **Configurações de pagamento** do WhatsApp, com cobrança em reais pela Facebook Brasil. As respostas do Atrium são mensagens de serviço, grátis até 1.000 por mês por número. Para estudo, a fatura fica em zero.
7. **Crie o PIN de duas etapas** quando a Meta pedir, ou em **Gerenciador do WhatsApp → Números de telefone → o número → Verificação em duas etapas**. São 6 dígitos. Guarde num gerenciador de senhas.
8. **Registre o número na Cloud API.** Sem esse passo, o envio falha com o erro 133010. Depois de gerar o token do passo 7 deste guia, rode no Git Bash, com o id do número novo:

   ```bash
   read -s -p "Token: " WA_TOKEN; echo
   read -s -p "PIN de 6 dígitos: " WA_PIN; echo
   curl -s -X POST "https://graph.facebook.com/v23.0/<id do número novo>/register" -H "Authorization: Bearer $WA_TOKEN" -H "Content-Type: application/json" -d "{\"messaging_product\":\"whatsapp\",\"pin\":\"$WA_PIN\"}"
   ```

   A resposta `{"success":true}` confirma. Se a tela da Meta já mostrar o número como **Conectado**, o registro já foi feito e o comando também devolve sucesso.
9. **Anote os ids do número novo.** Em **Etapa 1. Experimente**, escolha o número novo em **Seu número de teste**, ou abra o Gerenciador do WhatsApp:
   - **Phone Number ID** do número novo: vai em `WHATSAPP_PHONE_NUMBER_ID`.
   - **Identificação da conta de mensagens**: vai em `WHATSAPP_BUSINESS_ACCOUNT_ID`. Se o número entrou numa conta nova, e não na de teste, o id muda.

### Quando o estudo terminar

1. No Gerenciador do WhatsApp, abra **Números de telefone**, escolha o número e clique em **Excluir**. Assim, quem receber esse número da operadora no futuro não cai na sua conta.
2. Na Railway, grave `WHATSAPP_ENABLED=false`.
3. Remova o eSIM no iPhone, em Ajustes → Celular → o número → **Apagar eSIM**, e deixe de recarregar. A operadora cancela a linha pré-paga depois de um tempo sem recarga.

## 5. Chave secreta do app

1. No painel do app, abra **Configurações do app → Básico** (App settings → Basic), pelo ícone de engrenagem.
2. Em **Chave secreta do app** (App secret), clique em **Mostrar** e confirme a senha.
3. O valor vai em `WHATSAPP_APP_SECRET`. É ele que assina cada webhook com `X-Hub-Signature-256`.

## 6. Token de verificação

É um valor que você inventa. A Meta o manda de volta na hora de verificar o webhook, e a API compara. Gere um valor aleatório para cada ambiente:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

O valor vai em `WHATSAPP_VERIFY_TOKEN`, e o mesmo valor é digitado no painel da Meta no passo 9.

## 7. Usuário do sistema e token permanente

O token do botão **Gerar token** da Etapa 1 vence em 24 horas. A API usa o token de um usuário do sistema, que não vence.

1. Em [business.facebook.com](https://business.facebook.com), abra **Configurações → Usuários → Usuários do sistema** (Settings → Users → System users).
2. Clique em **Adicionar**, dê o nome `atrium-api` e a função **Funcionário** (Employee).
3. Clique em **Atribuir ativos** (Assign assets):
   - em **Apps**, escolha `atrium-dev` com controle total;
   - em **Contas do WhatsApp**, escolha a conta do número brasileiro com controle total.
4. Clique em **Gerar token** (Generate token), escolha o app `atrium-dev`, a validade **Nunca** e só estas duas permissões:
   - `whatsapp_business_messaging`
   - `whatsapp_business_management`
5. Copie o token na hora, porque a Meta não mostra de novo. Ele vai em `WHATSAPP_ACCESS_TOKEN`.

## 8. Variáveis na Railway

No projeto da Railway, ambiente `development`, serviço `api`, aba **Variables**:

| Variável | Valor |
|---|---|
| `WHATSAPP_ENABLED` | `false` por enquanto |
| `WHATSAPP_PHONE_NUMBER_ID` | Do número brasileiro, passo 4 |
| `WHATSAPP_BUSINESS_ACCOUNT_ID` | Da conta do número brasileiro, passo 4 |
| `WHATSAPP_APP_SECRET` | Do passo 5 |
| `WHATSAPP_VERIFY_TOKEN` | Do passo 6 |
| `WHATSAPP_ACCESS_TOKEN` | Do passo 7 |

Gravar uma variável na Railway republica o serviço com o commit do topo da `main`, sem passar pela aprovação do pipeline. Grave com `WHATSAPP_ENABLED=false`: com o canal desligado, a API ignora as outras e sobe normalmente.

`WHATSAPP_GRAPH_VERSION` não precisa ser gravada. O padrão fica no código e muda por PR.

## 9. Webhook

Só funciona depois que o código da Fase 18 estiver publicado em development e `WHATSAPP_ENABLED` estiver `true` lá, porque a rota só existe com o canal ligado.

1. No painel do app, abra **Configuração básica → Etapa 2. Configuração de produção → Configurar webhooks**.
2. Preencha:
   - **URL de callback**: `https://<url da Vercel de development>/backend/v1/whatsapp/webhook`
   - **Verificar token**: o valor de `WHATSAPP_VERIFY_TOKEN` de development
3. Clique em **Verificar e salvar**. A Meta chama o `GET` da rota, e a API devolve o desafio.
4. Nos campos do webhook, assine **messages**. É esse campo que traz as mensagens recebidas e os status de entrega.
5. Do seu WhatsApp pessoal, mande uma mensagem para o número brasileiro. A resposta do Atrium chega em alguns segundos.

Se a verificação falhar, confira três coisas: o caminho termina em `/backend/v1/whatsapp/webhook`, o token é o mesmo nos dois lados, e o deploy com `WHATSAPP_ENABLED=true` terminou.

Se a verificação passar e as mensagens não chegarem, a Meta pode estar segurando os webhooks porque o app não está publicado: a Etapa 2 avisa que, sem publicar, só chegam os webhooks de teste do painel. Publique o app em **Publicar** (Publish), no menu da esquerda. A Meta pede a URL da política de privacidade e a de exclusão de dados: use `https://<url da Vercel>/privacy` nas duas, porque a página explica o APAGAR DADOS. Ela pede também um ícone de 1024×1024 e uma categoria.

## 10. Testar na sua máquina, sem publicar o código

Para ver o webhook chegando na API local antes de publicar o código:

1. Suba a API com `uv run uvicorn app.main:app --reload` e, no `apps/api/.env`, `WHATSAPP_ENABLED=true` e as variáveis do passo 8.
2. Abra um túnel HTTPS para a porta 8000 com uma ferramenta de túnel, como o `cloudflared tunnel --url http://localhost:8000`.
3. Aponte o webhook do passo 9 para `https://<endereço do túnel>/v1/whatsapp/webhook`. Localmente não há `/backend`, porque não há Vercel, e o segredo da borda fica desligado.
4. Volte o webhook para a Vercel de development quando terminar.

## 11. Produção (Etapa 18.6)

1. **Número de produção.** Para um uso que vai durar, use uma linha que você mantenha: um pós-pago ou um fixo. O passo 4 vale igual, com um nome de exibição definitivo.
2. **Forma de pagamento.** Sem ela, a Meta para as mensagens de serviço depois das 1.000 grátis do mês.
3. Repita os passos 5 a 9 para o ambiente `production`, com um token de verificação próprio e o webhook apontado para a Vercel de production. O segredo e o token podem ser de um app separado, `atrium-prod`, o que é recomendado.
4. Ligue `WHATSAPP_ENABLED=true` em production só depois da sua aprovação na Etapa 18.6.

## Erros que aparecem nos testes

| Código | O que significa | O que fazer |
|---|---|---|
| 130497 | A conta não pode enviar para o país do destinatário | Use um número brasileiro, como no passo 4 |
| 131030 | O destinatário não está na lista do número de teste | Cadastre o número em **Destinatário**, na Etapa 1 |
| 131047 | A janela de 24 horas terminou | A pessoa precisa mandar mensagem de novo. O Atrium nunca inicia conversa |
| 133010 | O número não está registrado na Cloud API | Rode o registro do passo 4, item 8 |
| 190 | O token venceu ou foi revogado | Gere outro token no usuário do sistema, como na rotação abaixo |

Para números brasileiros, o `wa_id` que a Meta manda pode vir sem o 9 depois do DDD, como `554184208843`. O Atrium responde ao BSUID ou ao `wa_id` que a Meta mandou, nunca a um número digitado, então isso não atrapalha o canal.

## Ferramentas opcionais

- **WhatsApp Business Tools MCP**, servidor oficial da Meta, em fase inicial. Cria a conta, registra número, configura webhook e manda mensagem de teste pelo Claude Code. É para desenvolvimento, não para envio em produção.

  ```bash
  claude mcp add --transport http whatsapp_business_tools https://mcp.facebook.com/whatsapp_business_tools
  ```

  Depois rode `/mcp` no Claude Code e entre com a conta da Meta.
- Evite servidores MCP não oficiais que controlam o WhatsApp Web: eles podem levar ao banimento do número.

## Rotação do token

1. Gere um token novo no usuário do sistema (passo 7).
2. Grave em `WHATSAPP_ACCESS_TOKEN` na Railway e espere o deploy.
3. Em **Usuários do sistema**, revogue o token antigo.
4. Mande uma mensagem de teste e confira o alerta "Envio falhando" sem disparar.
