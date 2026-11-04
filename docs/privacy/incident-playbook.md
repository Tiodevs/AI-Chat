# Roteiro de incidentes — Atrium

Roteiro da seção 11.10 do SDD, conforme a Resolução CD/ANPD nº 15/2024. É desenho técnico da versão 1, não parecer jurídico.

Um incidente é qualquer evento que comprometa a confidencialidade, a integridade ou a disponibilidade de dados pessoais: acesso indevido ao banco, chave vazada, log ou rastro com dado que deveria ter sido redigido, perda de dados.

## 1. Conter

Faça na primeira hora, na ordem que couber:

- Revogue a chave vazada e gere outra: `GEMINI_API_KEY`, `LANGSMITH_API_KEY`, `RATE_LIMIT_HMAC_KEY`, `PSEUDONYM_KEY`, `METRICS_TOKEN`, a senha do banco ou os tokens do GitHub, da Railway e da Vercel.
- Encerre as sessões afetadas. Para todas: `DELETE FROM auth_sessions;` no banco do ambiente afetado.
- Remova o acesso de quem não deveria tê-lo, inclusive admins (seção 10.5).
- Preserve as evidências antes de apagar qualquer coisa: logs da Railway, rastros, `audit_events` e o horário de cada ação.

## 2. Avaliar

Responda por escrito:

- Que dados foram afetados? Algum é sensível, como dado de saúde?
- Quantos titulares?
- O dado estava protegido, por hash, HMAC ou pseudônimo?
- Qual a probabilidade de dano: discriminação, fraude, exposição?
- O incidente continua acontecendo?

## 3. Comunicar

Quando o incidente puder gerar risco ou dano relevante aos titulares:

- Comunique a ANPD em até 3 dias úteis do conhecimento, pelo formulário da ANPD.
- Comunique os titulares no mesmo prazo, em linguagem simples: o que aconteceu, que dados, o que foi feito e o que a pessoa pode fazer.
- Use o contato de `PRIVACY_CONTACT_EMAIL` como remetente e ponto de resposta.

Sem risco relevante, não há comunicação obrigatória, mas o registro abaixo continua obrigatório.

## 4. Registrar

Registre todo incidente, mesmo sem comunicação, e guarde o registro por 5 anos, fora do banco da aplicação. O registro tem:

| Campo | Conteúdo |
|---|---|
| Data e hora do conhecimento | |
| Data e hora estimada do início | |
| Descrição | O que aconteceu, sem copiar o dado pessoal |
| Dados e titulares afetados | Categorias e quantidade |
| Avaliação de risco | Resultado do passo 2 |
| Medidas de contenção | O que foi feito e quando |
| Comunicações | ANPD e titulares, com data, ou o motivo de não comunicar |
| Lições | O que muda no sistema ou no processo |

## 5. Depois

- Abra uma pull request com a correção e cite o incidente sem dado pessoal.
- Atualize o `ropa.md`, o `ripd.md` ou este roteiro se algo mudou.
