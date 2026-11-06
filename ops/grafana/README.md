# grafana

Painéis, fonte de dados e alertas em arquivos. Seção 18.3 do SDD.

Serviço `grafana` do ambiente `production`, construído pelo `Dockerfile` desta pasta e publicado com `railway up ops/grafana --path-as-root --service grafana` (seção 22.3), com um volume em `/var/lib/grafana`. A configuração do serviço fica na Railway (ADR-013).

| Variável | Valor |
|---|---|
| `PROMETHEUS_URL` | `http://prometheus.railway.internal:9090` |
| `ALERT_EMAIL` | e-mail de quem opera; vários separados por `;` |
| `GF_SECURITY_ADMIN_PASSWORD` | senha do administrador, só na Railway |
| `GF_SMTP_ENABLED`, `GF_SMTP_HOST`, `GF_SMTP_USER`, `GF_SMTP_PASSWORD`, `GF_SMTP_FROM_ADDRESS` | SMTP de quem envia o alerta. Sem eles o Grafana avalia os alertas e não consegue enviar o e-mail. |

## Conteúdo

| Caminho | O que é |
|---|---|
| `dashboards/*.json` | Os quatro painéis: saúde da API, qualidade de IA, cadastro e privacidade |
| `provisioning/datasources/prometheus.yaml` | Fonte de dados `prometheus` (uid fixo, usado pelos painéis e alertas) |
| `provisioning/dashboards/atrium.yaml` | Carrega os painéis de `/etc/grafana/dashboards` |
| `provisioning/alerting/alerting.json` | Os oito alertas, o contato por e-mail e a política de notificação |

Os arquivos YAML contêm JSON, que o YAML aceita; o Grafana só lê datasources e provedores com a extensão `.yaml`.

## Painéis e alertas versionados

Os painéis são provisionados e não editáveis na interface (`allowUiUpdates: false`). Para mudar um, edite o JSON e faça o deploy.

A "prontidão" do painel de saúde usa `up{job="atrium-api"}`: a API responde à coleta. A sonda `/ready` do banco não vira métrica.

O alerta "Retenção parada" dispara também sem dados, porque a ausência da série significa que o job nunca rodou.

Um contador que nasce já com valor 1 não gera `increase` na primeira coleta. Um primeiro erro de ingestão logo depois de um deploy pode passar sem alerta.
