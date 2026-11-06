# Roteiro do teste de usabilidade

Etapa 9.2 do [plano de ação](../plano-de-acao.md) e seção 15.9 do SDD. O teste valida as jornadas J1 a J5 com pessoas antes do deploy público. Um problema de severidade alta bloqueia a publicação.

Os resultados vão em [registro.csv](registro.csv), uma linha por pessoa e tarefa, e em [resultados.md](resultados.md), o resumo e a lista de problemas.

## Quem participa

São 5 pessoas por persona de visitante, 10 no total. A persona Ana, operadora, fica fora deste teste, porque as jornadas J1 a J5 são de visitante.

| Persona | Quem recrutar | Tarefas | Duração |
|---|---|---|---|
| Marta | 60 anos ou mais, usa o celular para mensagens e pouco além disso, não trabalha com tecnologia | J1 e J2 | Cerca de 20 minutos |
| Diego | 25 a 45 anos, usa aplicativos no celular todo dia, acompanha alguém em consultas ou exames | J1, J3, J5 e J4, nesta ordem | Cerca de 40 minutos |

Ninguém do projeto participa como usuário. Uma pessoa que já viu o Atrium conta como teste piloto, não como participante.

## Antes da primeira sessão

1. **A produção precisa da chave do Gemini.** Sem `GEMINI_API_KEY` na Railway, o chat responde só com a mensagem de indisponibilidade, e J1, J3 e J4 não podem ser testadas. Confira antes: pergunte "Qual é o horário de visita?" em `https://atrium-gold.vercel.app/` e veja a resposta com a fonte.
2. **Um celular de teste,** com o navegador atualizado e a tela gravada só se a pessoa autorizar. Use a mesma URL de produção para todos.
3. **Rede.** Cada pessoa da persona Diego faz dois cadastros, e a API aceita 20 mensagens de cadastro por hora por IP (seção 10.4). Use os dados móveis do celular de teste, ou deixe uma hora entre duas sessões de Diego na mesma rede.
4. **Navegador limpo para cada pessoa.** Abra uma aba anônima nova, ou apague os dados do site, para a pessoa começar como convidado, sem a conversa de quem veio antes.
5. **Cartão de dados fictícios.** Cada pessoa da persona Diego recebe um cartão com nome, e-mail e senha de teste. Ninguém digita dado pessoal real (seção 2.1, D-3). Os cartões estão no fim deste roteiro.
6. **Um teste piloto** com alguém de fora do projeto, para acertar o tempo e o texto dos cenários. O piloto não entra na contagem.

## Abertura da sessão

Leia em voz alta, com as suas palavras:

> Obrigado por ajudar. Estamos testando o site de um hospital fictício, não você. Se algo der errado, a culpa é do site, e é isso que queremos descobrir. Vou pedir algumas tarefas. Enquanto faz, pense em voz alta: diga o que está procurando, o que espera que aconteça e o que te confunde. Eu não vou ajudar durante a tarefa, a não ser que você peça ou fique preso. Use só os dados do cartão, nunca os seus. Podemos parar a qualquer momento. Posso gravar a tela do celular, sem o seu rosto?

Anote a resposta sobre a gravação. Sem autorização, não grave.

## Como conduzir

- Leia o cenário da tarefa exatamente como está e entregue o celular na tela indicada.
- Comece a contar o tempo quando a pessoa tocar na tela pela primeira vez. Pare quando ela disser que terminou ou quando o tempo limite acabar.
- Não aponte para a tela. Se a pessoa perguntar, devolva a pergunta: "O que você acha que deve fazer?".
- Ajude só se a pessoa pedir ou ficar parada por mais de 1 minuto. Anote cada ajuda.
- Ao fim de cada tarefa, pergunte: "De 1 a 7, quanto foi fácil fazer isso?", em que 1 é muito difícil e 7 é muito fácil.

### Resultado da tarefa

| Resultado | Quando usar |
|---|---|
| `sucesso` | Cumpriu o critério de sucesso sem ajuda, dentro do tempo limite |
| `sucesso com ajuda` | Cumpriu o critério depois de uma ou mais ajudas |
| `falha` | Não cumpriu o critério, desistiu ou passou do tempo limite |

## Tarefas

### J1. Horário de visita, sem cadastro

- **Quem:** todas as pessoas.
- **Começa em:** `https://atrium-gold.vercel.app/`, aba anônima nova.
- **Cenário:** "Uma pessoa da sua família está internada no Harborlight e você quer visitá-la hoje. Descubra até que horas pode visitar."
- **Sucesso:** a pessoa diz o horário certo e não cria conta. Para Diego, peça também: "E dá para ver de onde veio essa informação?". Sucesso se ela abrir ou apontar as fontes.
- **Tempo limite:** 3 minutos.
- **Gabarito:** visitas das 11:00 às 20:00, com silêncio das 13:00 às 14:00 (documento de visitas).
- **Observe:** se usa uma sugestão pronta ou digita, se entende a resposta, se acha as fontes, se o tamanho do texto incomoda.

### J2. Um sintoma

- **Quem:** persona Marta.
- **Começa em:** a conversa da J1, sem recarregar.
- **Cenário:** "Agora imagine que você está com uma dor forte no peito. Pergunte ao assistente o que fazer."
- **Sucesso:** a pessoa entende que o assistente não dá orientação médica e diz o que faria: ligar para a emergência ou ir à entrada de emergência.
- **Tempo limite:** 2 minutos.
- **Gabarito:** a resposta fixa não avalia sintomas, manda ligar para o número local de emergência e diz que a entrada de emergência fica no lado oeste, aberta 24 horas.
- **Observe:** se a recusa soa clara ou fria, se a pessoa insiste, se ela entende que a mensagem não ficou guardada.

### J3. Cadastro pela conversa, pulando o opcional

- **Quem:** persona Diego.
- **Começa em:** `https://atrium-gold.vercel.app/`, a mesma aba da J1.
- **Cenário:** "Você quer guardar as informações do hospital. Crie uma conta conversando com o assistente, com os dados do seu cartão. Não quer informar o telefone."
- **Sucesso:** a conta é criada com o nome e o e-mail do cartão, sem telefone, com os aceites. A pessoa chega à página da conta.
- **Tempo limite:** 7 minutos.
- **Use do cartão:** o e-mail da J3 e a senha.
- **Observe:** se a pessoa entende que pode pular, se confia no passo da senha fora do chat, se lê os aceites, onde hesita.

### J5. Exportar os dados e excluir a conta

- **Quem:** persona Diego, logo depois da J3, com a conta aberta.
- **Começa em:** a página da conta.
- **Cenário:** "Antes de ir embora, você quer uma cópia dos seus dados e depois quer apagar a sua conta."
- **Sucesso:** o arquivo da exportação é baixado, e a conta é excluída depois de uma confirmação. A pessoa vê que saiu da conta.
- **Tempo limite:** 5 minutos.
- **Observe:** se acha a aba de privacidade, se entende o que o arquivo contém, se a confirmação da exclusão é clara, se tem medo de apagar sem querer.

### J4. Do chat para o formulário

- **Quem:** persona Diego, depois da J5.
- **Começa em:** `https://atrium-gold.vercel.app/register`.
- **Cenário:** "Você começou a criar outra conta pela conversa, mas prefere preencher um formulário. Comece pela conversa, diga o seu nome e, depois, troque para o formulário e termine o cadastro lá."
- **Sucesso:** o formulário abre com o nome já preenchido, a pessoa completa o resto e a conta é criada. Nada do que ela disse no chat se perde.
- **Tempo limite:** 6 minutos.
- **Use do cartão:** o e-mail da J4 e a senha.
- **Observe:** se acha o link para o formulário, se percebe que o nome veio preenchido, se a senha está vazia e isso confunde.

Depois da J4, exclua a conta criada pela página da conta, para não deixar dado de teste em produção.

## Perguntas de fechamento

1. O que foi mais fácil?
2. O que foi mais difícil ou estranho?
3. Você usaria isso antes de ir ao hospital? Por quê?

## Severidade dos problemas

| Severidade | Quando usar | Efeito |
|---|---|---|
| Alta | Impede a tarefa, leva a um erro sério, expõe um dado ou faz a pessoa acreditar em algo falso sobre o hospital ou sobre saúde. Basta acontecer com uma pessoa. | Bloqueia o deploy público até a correção (seção 15.9) |
| Média | A pessoa conclui, mas com ajuda, com erro que ela mesma corrige ou com perda clara de tempo. Ou duas pessoas ou mais tropeçam no mesmo ponto. | Corrigir antes de abrir ao público, se der |
| Baixa | Incômodo que não muda o resultado, como um texto ambíguo ou um alvo pequeno que a pessoa acertou mesmo assim | Fica no registro para depois |

## Depois de cada sessão

- Preencha as linhas da pessoa em `registro.csv` no mesmo dia, enquanto a memória está fresca.
- Dê a cada problema um código, como `P1`, e use o mesmo código quando outra pessoa tropeçar nele. O código vai na coluna `problemas`.
- Apague as gravações quando o resultado estiver consolidado.

## Depois das 10 sessões

1. Consolide em `resultados.md`: a taxa de sucesso por tarefa, o tempo mediano e a lista de problemas com a severidade.
2. Abra uma PR por problema de severidade alta ou média, citando o código do problema. A IA faz as correções, como o plano prevê.
3. A Etapa 9.2 passa quando nenhum problema de severidade alta continua aberto (CA-1) e os resultados estão registrados em `docs/` (CA-2).

## Cartões de dados fictícios

Use um cartão por pessoa da persona Diego. Todos os e-mails são do domínio reservado `example.com`, que não recebe mensagens. A senha de teste é a mesma em todos os cartões e só vale para este teste.

Senha de teste: `Harborlight-teste-2026`

| Pessoa | Nome | E-mail da J3 | E-mail da J4 |
|---|---|---|---|
| D1 | Rafael Moreira | rafael.j3@example.com | rafael.j4@example.com |
| D2 | Camila Duarte | camila.j3@example.com | camila.j4@example.com |
| D3 | Bruno Teixeira | bruno.j3@example.com | bruno.j4@example.com |
| D4 | Larissa Campos | larissa.j3@example.com | larissa.j4@example.com |
| D5 | Thiago Nunes | thiago.j3@example.com | thiago.j4@example.com |

Se um e-mail já tiver conta, porque uma sessão anterior não excluiu, acrescente um número antes do `@`, como `rafael.j3.2@example.com`.
