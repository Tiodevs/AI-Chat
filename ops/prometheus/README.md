# prometheus

Coleta `GET /metrics` da API pela rede privada da Railway a cada 30 s. Seção 18.3 do SDD.

Serviço `prometheus` do ambiente `production`, com raiz em `ops/prometheus` e um volume em `/prometheus`. Não há serviço em `development`.

| Variável | Valor |
|---|---|
| `API_HOST` | `api.railway.internal` |
| `API_PORT` | a porta do serviço `api` (`$PORT`) |
| `METRICS_TOKEN` | o mesmo `METRICS_TOKEN` da API, como referência de variável da Railway |

A API escuta em `::`, para aceitar a rede privada. A coleta de produção é verificada na Etapa 10.2.

## Variáveis

O Prometheus não expande variáveis no arquivo de configuração. `entrypoint.sh` troca `${API_HOST}`, `${API_PORT}` e `${METRICS_TOKEN}` por `sed` antes de iniciar, e o serviço não sobe se alguma estiver vazia.

## Conferir localmente

A raiz do repositório tem um `docker-compose.yml` que sobe o Prometheus junto com a API, o banco e o Grafana. Os alvos aparecem em `http://localhost:9090/targets`.

## Nomes das séries

O `prometheus_client` acrescenta `_total` aos contadores. A tabela da seção 18.3 lista `atrium_http_requests`, e a série coletada é `atrium_http_requests_total`.

`atrium_dsr_open`, `atrium_retention_deleted_total` e `atrium_retention_last_run_timestamp_seconds` vêm do banco a cada coleta. O `retention-job` roda em outro processo e grava cada execução em `retention_runs`.
