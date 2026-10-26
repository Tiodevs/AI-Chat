# ADR-006 — Políticas de rastro

## Contexto

Uma pergunta pode conter dado de saúde. O rastro de IA não pode levar essa pergunta. A seção 18.4 do SDD define o quanto de cada passo vai ao LangSmith.

## Decisão

Políticas de rastro por passo, com metadados apenas onde pode haver dado de saúde.

## Consequências

Menos contexto em alguns rastros, em troca de cumprir a LGPD.

## Alternativas

Rastrear tudo. Desligar o LangSmith.
