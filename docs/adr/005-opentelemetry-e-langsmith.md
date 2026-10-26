# ADR-005 — OpenTelemetry e LangSmith

## Contexto

Depois de uma resposta ruim, o operador precisa ver o tempo gasto no sistema e o que o modelo recebeu, recuperou e respondeu. O `request_id` liga os sinais. A seção 18 do SDD divide esse trabalho.

## Decisão

OpenTelemetry para o sistema e LangSmith para a IA, ligados por `request_id` e `trace_id`.

## Consequências

Cada ferramenta faz o que faz melhor. Dois lugares para olhar, ligados por id.

## Alternativas

Só OpenTelemetry. Só LangSmith.
