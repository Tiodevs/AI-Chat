# Relatório de impacto à proteção de dados — Atrium

Relatório do art. 38 da Lei nº 13.709/2018, para a versão 1 com dados fictícios. É desenho técnico, não parecer jurídico. Se pessoas reais passarem a usar o Atrium, este relatório precisa ser refeito com revisão jurídica antes disso.

## 1. Descrição do tratamento

O Atrium responde perguntas públicas sobre um hospital fictício e permite criar conta por conversa ou por formulário. Os dados, as finalidades, as bases legais e os prazos estão em `ropa.md`.

O tratamento usa um modelo de linguagem externo (Gemini) e um serviço de rastros de IA (LangSmith). Os dois ficam nos Estados Unidos.

## 2. Necessidade e proporcionalidade

- Só nome e e-mail são obrigatórios. Telefone, tipo de visitante e motivo da visita são opcionais.
- Tipo de visitante e motivo da visita são listas fechadas, sem texto livre, e dependem do consentimento específico do art. 11, I.
- Mensagens que pedem orientação médica não são gravadas.
- O IP só existe como HMAC com sal diário.
- Cada dado tem prazo na seção 11.6, aplicado pela tarefa `retention-job`.

## 3. Riscos e medidas

| Risco | Probabilidade | Impacto | Medidas | Risco residual |
|---|---|---|---|---|
| A pessoa conta algo sobre a própria saúde na pergunta | Alta | Alto | Aviso no compositor, classificação `medical_advice` com conteúdo descartado antes de gravar, histórico lido do banco, rastro só com o desfecho (seção 11.4) | Médio: o texto ainda passa pelo Gemini de forma transitória |
| Os campos opcionais indicam que a pessoa é paciente | Média | Alto | Consentimento destacado, campos escondidos sem a personalização, revogação que apaga os dois campos na hora | Baixo |
| Um admin lê conversas de um titular identificado | Média | Médio | Pseudonimização, conteúdo só de convidados e de membros com o consentimento de melhoria, revelação com motivo gravado em `identity.reveal` | Baixo |
| Vazamento do banco | Baixa | Alto | Rede privada da Railway, senhas com argon2id, tokens e IPs só com hash, retenção curta | Médio |
| Rastros no LangSmith identificam a pessoa | Baixa | Médio | Anonimizador antes de sair do processo, pseudônimo com chave secreta, políticas por passo (`lia.md`) | Baixo |
| Transferência internacional sem garantia | Baixa | Médio | Art. 33 com as cláusulas contratuais dos provedores, lista de operadores no Aviso | Baixo |
| Conta de convidado não consegue exercer direitos | Média | Baixo | Canal do titular sem conta, prazo de 15 dias, retenção de 30 dias | Baixo |
| Abuso do canal do titular | Média | Baixo | Limite de 5 pedidos por IP no dia (seção 10.4) | Baixo |
| WhatsApp: a pessoa manda foto de exame ou receita | Alta | Alto | Aviso antes da primeira resposta, mídia não baixada, resposta fixa (seção 30.9.5) | Médio: a foto fica na Meta, pelo prazo dos termos dela |
| WhatsApp: a pessoa conta algo de saúde por texto | Alta | Alto | Classificação, recusa sem gravar conteúdo, remoção no atendimento | Médio |
| WhatsApp: o número de telefone vaza | Baixa | Médio | O BSUID é a identidade; o número fica só em `whatsapp_contacts.phone`, nunca em log, rastro, métrica, console nem exportação, e some com o contato em 30 dias (D-12, ADR-018) | Baixo |
| WhatsApp: o token da Meta vaza e alguém manda mensagem pelo número | Baixa | Alto | Segredo só no serviço `api`, usuário do sistema com dois escopos, alerta "Envio falhando" no erro 190, rotação em `docs/whatsapp-configuracao-na-meta.md` | Baixo |
| WhatsApp: a Meta muda a política de IA e bloqueia o número | Baixa | Médio | Bot restrito ao hospital, recusa fora do tema, nenhuma mensagem iniciada pelo Atrium | Baixo |
| WhatsApp: um aparelho compartilhado mostra a conversa a outra pessoa | Média | Médio | Fora do controle do Atrium. O aviso ensina APAGAR DADOS | Médio |

## 4. Direitos do titular

Exportação, correção, gestão de consentimentos e exclusão imediatas na página da conta. Os demais pedidos, inclusive de convidados, pelo canal em `/privacy`, com prazo de 15 dias corridos (seção 11.5).

## 5. Conclusão

Com dados fictícios, o risco residual é aceitável para uma implantação de estudo. O risco que continua médio é o texto livre com dado de saúde passando pelo Gemini. Antes de qualquer uso com pessoas reais, a produção precisa do projeto Google com faturamento ativo (seção 11.4, item 6) e de revisão jurídica deste relatório.
