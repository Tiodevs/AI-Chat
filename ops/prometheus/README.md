# prometheus

Coleta `GET /metrics` da API pela rede privada da Railway a cada 30 s e guarda as séries por 30 dias, para o Grafana ler. Infraestrutura de observabilidade, [seção 18.3 do SDD](../../docs/sdd/observabilidade.md#183-métricas-painéis-e-alertas) e [ADR-009](../../docs/adr/009-prometheus-grafana.md).

## Arquivos

| Arquivo | O que faz | Quem usa |
|---|---|---|
| [`Dockerfile`](Dockerfile) | Imagem `prom/prometheus:v3.5.0` com a configuração e o `entrypoint.sh` | Serviço `prometheus` da Railway, só em production, e o do `docker-compose.yml` |
| [`entrypoint.sh`](entrypoint.sh) | Confere `API_HOST`, `API_PORT` e `METRICS_TOKEN`, troca os marcadores do `prometheus.yml` por `sed` numa cópia em `/tmp` e inicia o Prometheus com o volume em `/prometheus` e 30 dias de retenção | O `ENTRYPOINT` da imagem |
| [`prometheus.yml`](prometheus.yml) | Um job, `atrium-api`: `http://${API_HOST}:${API_PORT}/metrics` com `Authorization: Bearer`, a cada 30 s | O Prometheus, depois do `entrypoint.sh` |
| `README.md` | Este arquivo | |

## Serviço na Railway

Serviço `prometheus` do ambiente `production`, construído pelo `Dockerfile` desta pasta e publicado com `railway up --service prometheus`, da raiz do repositório, com o diretório raiz do serviço em `/ops/prometheus` (seção 22.3) e um volume em `/prometheus`. A configuração do serviço fica na Railway (ADR-013). Não há serviço em `development`.

| Variável | Valor |
|---|---|
| `API_HOST` | `api.railway.internal` |
| `API_PORT` | A porta do serviço `api` (`$PORT`, 8080 pela seção 22.1) |
| `METRICS_TOKEN` | O mesmo `METRICS_TOKEN` da API, como referência de variável da Railway |

A API escuta em `0.0.0.0` (Dockerfile da API e seção 22.1), e os ambientes da Railway criados depois de 16/10/2025 resolvem a rede privada também em IPv4. A seção 18.3 ainda diz que a API escuta em `::`. A coleta de produção foi conferida na Etapa 10.2.

## Como ler

1. `prometheus.yml`: o intervalo global e o único job.
2. `entrypoint.sh`: como os marcadores viram valores. O Prometheus não expande variáveis no arquivo de configuração, e o serviço não sobe se alguma das três estiver vazia. Um comentário do `prometheus.yml` que contivesse um dos três marcadores também seria trocado, por isso eles só aparecem nos valores.
3. `Dockerfile`: a imagem e o volume.

**O que é observado.** Só a API. O job `atrium-api` traz as séries `atrium_*` da tabela da seção 18.3 e a série `up`, que o Prometheus cria para cada alvo: 1 quando a coleta respondeu, 0 quando falhou. O banco, o `retention-job` e o frontend não são alvos.

**Nomes das séries.** O `prometheus_client` acrescenta `_total` aos contadores. A tabela da seção 18.3 lista `atrium_http_requests`, e a série coletada é `atrium_http_requests_total`.

**Séries que vêm do banco.** `atrium_dsr_open`, `atrium_retention_deleted_total` e `atrium_retention_last_run_timestamp_seconds` não são contadas no processo da API: o `GET /metrics` as lê do banco a cada coleta. O `retention-job` roda em outro processo e grava cada execução em `retention_runs`. Antes da primeira leitura com sucesso, essas séries não aparecem.

**Sem regras aqui.** O `evaluation_interval` existe, mas não há arquivo de regras: os oito alertas são avaliados pelo Grafana ([`ops/grafana`](../grafana/README.md)).

**Uma réplica.** Um alvo fixo basta porque a API tem uma réplica na versão 1 (ADR-012). A seção 6.5 descreve a descoberta pelo DNS privado para mais réplicas.

## Testes

`apps/api/tests/unit/test_ops_files.py` confere que este `prometheus.yml` coleta a cada 30 s, em `/metrics` e com o marcador do token, e que toda consulta dos painéis e alertas usa uma série que a API expõe. Em `apps/api`:

```bash
uv run pytest tests/unit/test_ops_files.py
```

Para conferir de verdade, suba a pilha local com `docker compose up --build` na raiz do repositório. Os alvos aparecem em `http://localhost:9090/targets`, e o alvo `atrium-api` fica `UP` quando o token do Prometheus e o da API são iguais.

## Leia também

- [SDD 18.3](../../docs/sdd/observabilidade.md#183-métricas-painéis-e-alertas): as métricas, os painéis e os alertas.
- [SDD 22.1](../../docs/sdd/entrega.md#221-railway) e [22.3](../../docs/sdd/entrega.md#223-github-actions): o serviço e o deploy.
- [ADR-009](../../docs/adr/009-prometheus-grafana.md) e [ADR-013](../../docs/adr/013-railway-configurada-pela-api.md).
- [`ops/grafana`](../grafana/README.md), que lê este Prometheus.
- [Guia, parte 10](../../docs/guia/10-observabilidade.md) e [parte 14](../../docs/guia/14-entrega-e-operacao.md).
