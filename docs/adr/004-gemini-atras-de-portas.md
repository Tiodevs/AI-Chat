# ADR-004 — Gemini atrás de portas

## Contexto

A aplicação depende de portas próprias de chat e de embedding. A execução padrão dos testes não pode chamar um modelo ao vivo. A seção 17 do SDD define as portas e os adaptadores falsos.

## Decisão

Gemini atrás de portas, com falsos determinísticos nos testes.

## Consequências

CI rápida e gratuita. A qualidade real é medida nas avaliações.

## Alternativas

Testes com o modelo real.
