# ADR-008 — Entrega pelo GitHub Actions

## Contexto

A publicação em development e em produção precisa de um pipeline só, com testes de fumaça e um portão humano antes da produção. A seção 22 do SDD descreve esse fluxo.

## Decisão

Entrega pelo GitHub Actions com aprovação para produção.

## Consequências

Um pipeline só, com testes de fumaça e portão humano.

## Alternativas

Integrações de Git da Vercel e da Railway.
