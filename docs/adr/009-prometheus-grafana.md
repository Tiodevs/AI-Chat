# ADR-009 — Prometheus e Grafana

## Contexto

As métricas precisam de coletor, painéis e alertas. A API, o banco e os painéis ficam na mesma rede privada. A seção 18.3 do SDD descreve a coleta.

## Decisão

Prometheus e Grafana na Railway.

## Consequências

Tudo no mesmo projeto e na mesma rede privada. Mais dois serviços para manter.

## Alternativas

Grafana Cloud. Só as métricas da plataforma.
