# ADR-003 — Máquina de estados do cadastro

## Contexto

O cadastro cria uma conta. Um modelo não pode decidir que a conta existe, definir o papel, registrar consentimento nem fornecer a senha. A seção 7.2 do SDD separa a transição de estado da extração feita pelo modelo.

## Decisão

Máquina de estados do cadastro em Python puro, com LangGraph só orquestrando.

## Consequências

Comportamento previsível e testável. A IA fica restrita a extrair e formular.

## Alternativas

Agente de IA livre com ferramentas para criar a conta.
