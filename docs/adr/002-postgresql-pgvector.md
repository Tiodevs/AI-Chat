# ADR-002 — PostgreSQL com pgvector

## Contexto

O PostgreSQL é o sistema de registro de perfis, consentimentos, sessões, documentos, chunks e vetores. Os uploads da versão 1 cabem no banco. A seção 8 do SDD descreve o desenho.

## Decisão

PostgreSQL com pgvector como único armazenamento.

## Consequências

Uma transação cobre dados e vetores. Escala de arquivos limitada.

## Alternativas

Banco vetorial separado. Bucket para arquivos.
