# grafana

Painéis, fonte de dados e alertas do Grafana em arquivos, provisionados pela imagem desta pasta e lidos do Prometheus. Infraestrutura de observabilidade, [seção 18.3 do SDD](../../docs/sdd/observabilidade.md#183-métricas-painéis-e-alertas) e [ADR-009](../../docs/adr/009-prometheus-grafana.md).

## Arquivos

| Arquivo | O que faz | Quem usa |
|---|---|---|
| [`Dockerfile`](Dockerfile) | Imagem `grafana/grafana:12.1.0` com `provisioning/` em `/etc/grafana/provisioning` e `dashboards/` em `/etc/grafana/dashboards` | Serviço `grafana` da Railway, só em production, e o do `docker-compose.yml` |
| [`dashboards/api-health.json`](dashboards/api-health.json) | Painel "Atrium, saúde da API" | O provedor `atrium` |
| [`dashboards/ai-quality.json`](dashboards/ai-quality.json) | Painel "Atrium, qualidade de IA" | O provedor `atrium` |
| [`dashboards/registration.json`](dashboards/registration.json) | Painel "Atrium, cadastro" | O provedor `atrium` |
| [`dashboards/privacy.json`](dashboards/privacy.json) | Painel "Atrium, privacidade" | O provedor `atrium` |
| [`provisioning/datasources/prometheus.yaml`](provisioning/datasources/prometheus.yaml) | Fonte de dados `Prometheus`, padrão, com o uid fixo `prometheus`, a URL de `${PROMETHEUS_URL}` e `timeInterval` de 30 s, o intervalo da coleta | Os painéis e os alertas, pelo uid |
| [`provisioning/dashboards/atrium.yaml`](provisioning/dashboards/atrium.yaml) | Provedor `atrium`: carrega os JSON de `/etc/grafana/dashboards` na pasta Atrium, sem edição pela interface (`allowUiUpdates: false`) nem exclusão (`disableDeletion: true`) | O Grafana, na subida |
| [`provisioning/alerting/alerting.json`](provisioning/alerting/alerting.json) | As oito regras do grupo `atrium`, o contato `atrium-operacao` no Discord, a política de notificação e a exclusão do contato de e-mail antigo | O Grafana, na subida |
| `README.md` | Este arquivo | |

Os arquivos `.yaml` contêm JSON, que o YAML aceita; o Grafana só lê fontes de dados e provedores de painel com extensão YAML. JSON não aceita comentário, então cada painel e cada alerta está explicado aqui.

## Serviço na Railway

Serviço `grafana` do ambiente `production`, construído pelo `Dockerfile` desta pasta e publicado com `railway up --service grafana`, da raiz do repositório, com o diretório raiz do serviço em `/ops/grafana` (seção 22.3) e um volume em `/var/lib/grafana`. A configuração do serviço fica na Railway (ADR-013).

| Variável | Valor |
|---|---|
| `PROMETHEUS_URL` | `http://prometheus.railway.internal:9090` |
| `DISCORD_WEBHOOK_URL` | URL do webhook do canal do Discord que recebe os alertas. É segredo: só na Railway, nunca no repositório. Sem ela o provisionamento recusa o contato e o Grafana não sobe, então grave antes do deploy. |
| `GF_SECURITY_ADMIN_PASSWORD` | Senha do administrador, só na Railway |

O contato era por e-mail, mas a Railway só libera SMTP de saída no plano Pro. O webhook do Discord usa HTTPS e funciona em qualquer plano. `ALERT_EMAIL` deixou de ser usada e pode sair do serviço.

## Painéis

Os quatro painéis abrem nas últimas 6 horas e se atualizam a cada minuto. Toda consulta usa a fonte de dados de uid `prometheus`.

| Painel (`uid`) | Gráfico | Consulta, em resumo |
|---|---|---|
| Atrium, saúde da API (`atrium-api-health`) | Pedidos por segundo | Taxa de `atrium_http_requests_total` em 5 min, por rota |
| | Erros 5xx (proporção) | Pedidos com `status` 5xx sobre o total, em 5 min |
| | Latência p95 por rota | `histogram_quantile(0.95)` de `atrium_http_request_duration_seconds`, por rota |
| | Prontidão (a API responde à coleta) | `up{job="atrium-api"}` |
| Atrium, qualidade de IA (`atrium-ai-quality`) | Desfechos por hora | Aumento de `atrium_qa_outcomes_total` em 1 h, por desfecho |
| | Similaridade do melhor trecho (p50 e p10) | Dois quantis de `atrium_qa_top_similarity`, em 1 h |
| | Primeiro token p95 | `histogram_quantile(0.95)` de `atrium_qa_first_token_seconds`, em 10 min |
| | Tokens por dia | Aumento de `atrium_llm_tokens_total` em 1 dia, por direção |
| | Orçamento diário usado | `max(atrium_llm_budget_ratio)`, num medidor |
| | Circuito do modelo aberto | `max(atrium_llm_circuit_open)` |
| Atrium, cadastro (`atrium-registration`) | Funil por etapa | Aumento de `atrium_registration_events_total` no intervalo do painel, por evento |
| | Eventos por caminho | O mesmo contador em 1 h, por caminho e evento |
| | Abandono (proporção dos iniciados) | `abandoned` sobre `started`, em 1 dia |
| | Concluídos por dia | `completed` em 1 dia, por caminho |
| Atrium, privacidade (`atrium-privacy`) | Pedidos de titular abertos | `max by (overdue) (atrium_dsr_open)` |
| | Eliminações por regra (24 h) | Aumento de `atrium_retention_deleted_total` em 1 dia, por regra |
| | Horas desde a última execução do retention-job | `time()` menos `atrium_retention_last_run_timestamp_seconds`, em horas |

## Alertas

As oito regras ficam no grupo `atrium`, na pasta Atrium, avaliadas a cada minuto. Cada uma tem três passos: `A` é a consulta ao Prometheus, `B` reduz a série ao último valor e `C` compara com o limiar. Todas levam o rótulo `service=atrium` e uma anotação `summary`.

| Alerta (`uid`) | Consulta | Dispara quando | Pendente por | Sem dados |
|---|---|---|---|---|
| Erros da API (`atrium-api-errors`) | Proporção de 5xx em 10 min | Acima de 0,02 | 10 min | OK |
| Latência de IA (`atrium-ai-latency`) | p95 do primeiro token em 10 min | Acima de 3 s | 30 min | OK |
| Qualidade em queda (`atrium-ai-quality`) | `abstained` mais `grounding_failed` sobre todos os desfechos, em 1 h | Acima de 0,25 | Na hora | OK |
| Orçamento (`atrium-llm-budget`) | `max(atrium_llm_budget_ratio)` | Acima de 0,8 | Na hora | OK |
| Circuito aberto (`atrium-llm-circuit`) | `max(atrium_llm_circuit_open)` | Acima de 0,5, ou seja, igual a 1 | 5 min | OK |
| Ingestão (`atrium-ingestion-failed`) | Aumento de `atrium_ingestion_versions_total{status="failed"}` em 1 h | Acima de 0 | Na hora | OK |
| Pedido de titular atrasado (`atrium-dsr-overdue`) | `max(atrium_dsr_open{overdue="true"})` | Acima de 0 | Na hora | OK |
| Retenção parada (`atrium-retention-stalled`) | Segundos desde a última execução do `retention-job` | Acima de 93.600 s (26 h) | Na hora | **Alerting** |

A política de notificação manda tudo para o contato `atrium-operacao`, agrupado por `alertname`: espera 30 s para juntar o primeiro grupo, 5 min entre grupos e repete a cada 4 h enquanto o alerta continua disparado.

## Como ler

Comece pelo `provisioning/datasources/prometheus.yaml` e pelo `provisioning/dashboards/atrium.yaml`, curtos, e depois um painel. O `alerting.json` é o maior arquivo: leia uma regra inteira e as outras seguem o mesmo molde.

- **Painéis versionados.** Os painéis são provisionados e não editáveis na interface (`allowUiUpdates: false`). Para mudar um, edite o JSON e faça o deploy.
- **Contato removido.** Tirar uma integração do `alerting.json` não a apaga: o Grafana a guarda no volume. Para apagar, liste o `uid` dela em `deleteContactPoints`. É assim que sai o e-mail antigo (`atrium-operacao-email`); a exclusão se repete a cada deploy sem erro.
- **Testar o contato.** Abra Alerting, Contact points e clique em View no `atrium-operacao`. A página é só de leitura, mas o botão Test fica ao lado da integração Discord.
- **Prontidão.** O gráfico de prontidão do painel de saúde usa `up{job="atrium-api"}`: a API responde à coleta. A sonda `/ready` do banco não vira métrica, então o painel não mostra a prontidão da seção 12.
- **Retenção parada sem dados.** O alerta dispara também quando a série não existe, porque a ausência dela significa que o job nunca rodou (seção 18.3).
- **Primeiro aumento.** Um contador que nasce já com valor 1 não gera `increase` na primeira coleta. Um primeiro erro de ingestão logo depois de um deploy pode passar sem alerta.
- **Fora do Grafana.** A página de qualidade do admin usa agregados do banco, não o Prometheus, para funcionar mesmo sem o Grafana (seção 18.3).

## Testes

`apps/api/tests/unit/test_ops_files.py` confere estes arquivos sem subir o Grafana: os quatro títulos da seção 18.3 com uids e ids de painel únicos e a fonte `prometheus`; os oito alertas com os passos `A`, `B` e `C`; os limiares e prazos da seção 18.3; o contato Discord lido de `${DISCORD_WEBHOOK_URL}`, sem URL de webhook no arquivo; a exclusão do e-mail antigo; e que toda consulta usa uma série que a API expõe. Em `apps/api`:

```bash
uv run pytest tests/unit/test_ops_files.py
```

Para ver os painéis, suba a pilha local com `docker compose up --build` na raiz e abra `http://localhost:3000`. O `docker-compose.yml` dá ao `DISCORD_WEBHOOK_URL` um valor que não leva a lugar nenhum, só para o Grafana subir.

## Leia também

- [SDD 18.3](../../docs/sdd/observabilidade.md#183-métricas-painéis-e-alertas): as métricas, os painéis e os alertas.
- [SDD 18.5](../../docs/sdd/observabilidade.md#185-o-que-um-operador-olha): o que um operador olha depois de uma resposta ruim.
- [SDD 22.1](../../docs/sdd/entrega.md#221-railway) e [22.3](../../docs/sdd/entrega.md#223-github-actions): o serviço e o deploy.
- [ADR-009](../../docs/adr/009-prometheus-grafana.md) e [ADR-013](../../docs/adr/013-railway-configurada-pela-api.md).
- [`ops/prometheus`](../prometheus/README.md), a fonte destes dados.
- [Guia, parte 10](../../docs/guia/10-observabilidade.md) e [parte 14](../../docs/guia/14-entrega-e-operacao.md).
