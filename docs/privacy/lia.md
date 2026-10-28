# Teste de legítimo interesse — rastros de IA

Este texto documenta o teste do art. 10 da Lei nº 13.709/2018 para os rastros enviados ao LangSmith. É desenho técnico da versão 1, não parecer jurídico. Na versão 1 os dados são fictícios. Se pessoas reais passarem a usar o Atrium, a revisão jurídica volta a ser necessária antes disso.

A decisão de usar a região dos Estados Unidos está na D-2. A transferência internacional está na seção 11.7 do SDD. As políticas de rastro estão na seção 18.4.

## Interesse

O interesse é diagnosticar e melhorar as respostas do assistente: ver o que foi recuperado, o que o modelo devolveu, o desfecho e a nota de útil ou não útil. Sem esse rastro, uma resposta ruim só aparece como um agregado no banco.

O interesse é do operador da implantação, em nome do hospital fictício. Não é interesse de marketing nem de vender dado.

## Necessidade

O log e o rastro de sistema não guardam o texto da pergunta nem os trechos recuperados. O LangSmith é a ferramenta que mostra esse conteúdo, e só onde a política permite.

O que pode seguir:

| Situação | O que sai |
|---|---|
| Classificação | `intent`, confiança, versão do prompt e tokens. Sem a pergunta e sem o histórico. |
| Pergunta pública | Pergunta reescrita, trechos, resposta, citações e desfecho, depois do anonimizador. |
| Orientação médica ou fora de tema | Só o desfecho. A pergunta original não sai. |
| Cadastro | Nomes dos campos, próximo passo e tokens. Nunca os valores. |
| Ingestão | O corpus público e fictício. |

O anonimizador troca e-mail por `[redacted-email]`, telefone por `[redacted-phone]` e sequência de seis ou mais dígitos por `[redacted-digits]`. O nome não é marcador. UUID e hash com letra permanecem, para o `request_id` e o pseudônimo continuarem utilizáveis.

O pseudônimo do titular é o HMAC do id do usuário ou da chave de convidado com `PSEUDONYM_KEY`. O id cru não entra no rastro. Quando a conta é apagada, o id deixa de existir e o rastro perde o vínculo com a pessoa.

A variável global `LANGSMITH_HIDE_INPUTS` não é usada. Com ela ligada, o anonimizador não roda. Cada política tem o próprio cliente: `full` anonimiza, `masked` filtra e anonimiza, `metadata_only` esconde entrada e saída. Uma chave de organização informa `LANGSMITH_WORKSPACE_ID`. Sem isso o LangSmith responde 403 e nenhum rastro sai.

A chamada ao modelo não usa o rastreamento automático do LangChain. O rastro é montado depois, só com os campos da política.

## Balanceamento

De um lado, o operador precisa entender uma resposta errada sem abrir o banco de outro titular. De outro, a pergunta pode conter dado de saúde mesmo sem o produto pedir.

O desenho fica do lado da minimização nesse conflito:

- a pergunta original não entra na classificação nem numa recusa médica;
- o conteúdo de uma mensagem médica também não é gravado no PostgreSQL;
- o que é público passa pelo anonimizador antes de sair;
- uma falha ao enviar a nota `user_helpful` fica no log e não muda a resposta do visitante;
- a chave do LangSmith existe só no processo da API.

A expectativa da pessoa está no Aviso de Privacidade, quando ele for publicado: o assistente é uma IA, dado de saúde não deve ser compartilhado, e rastros mascarados servem para qualidade. Não há titular real na versão 1.

## Salvaguardas

- Teste de cada política com nome, e-mail e telefone, conferindo o que sairia.
- Teste de que uma pergunta médica gera rastro só com o desfecho.
- A CI padrão não lê a chave do LangSmith e não chama o serviço.
- O `lifespan` chama `wait_for_all_tracers()` no desligamento, para um deploy não deixar rastro pela metade sem também não vazar o que a política escondeu.
- Retenção curta do plano do LangSmith, sem identificador direto, como na seção 11.6.

## Conclusão

O legítimo interesse sustenta os rastros mascarados de qualidade e diagnóstico, com as políticas acima. Não sustenta enviar a pergunta original quando ela pode ser dado de saúde, nem desligar o anonimizador por uma chave global. Se o uso deixar de ser fictício, este teste precisa ser refeito com revisão jurídica antes disso.
