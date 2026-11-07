# grafana

Painéis, fonte de dados e alertas em arquivos. Seção 18.3 do SDD.

Serviço `grafana` do ambiente `production`, construído pelo `Dockerfile` desta pasta e publicado com `railway up --service grafana`, da raiz do repositório, com o diretório raiz do serviço em `/ops/grafana` (seção 22.3), com um volume em `/var/lib/grafana`. A configuração do serviço fica na Railway (ADR-013).

| Variável | Valor |
|---|---|
| `PROMETHEUS_URL` | `http://prometheus.railway.internal:9090` |
| `DISCORD_WEBHOOK_URL` | URL do webhook do canal do Discord que recebe os alertas. É segredo: só na Railway, nunca no repositório. Sem ela o Grafana não sobe, então grave antes do deploy. |
| `GF_SECURITY_ADMIN_PASSWORD` | senha do administrador, só na Railway |

O contato era por e-mail, mas a Railway só libera SMTP de saída no plano Pro. O webhook do Discord usa HTTPS e funciona em qualquer plano. `ALERT_EMAIL` deixou de ser usada e pode sair do serviço.

## Conteúdo

| Caminho | O que é |
|---|---|
| `dashboards/*.json` | Os quatro painéis: saúde da API, qualidade de IA, cadastro e privacidade |
| `provisioning/datasources/prometheus.yaml` | Fonte de dados `prometheus` (uid fixo, usado pelos painéis e alertas) |
| `provisioning/dashboards/atrium.yaml` | Carrega os painéis de `/etc/grafana/dashboards` |
| `provisioning/alerting/alerting.json` | Os oito alertas, o contato no Discord e a política de notificação |

Os arquivos YAML contêm JSON, que o YAML aceita; o Grafana só lê datasources e provedores com a extensão `.yaml`.

## Painéis e alertas versionados

Os painéis são provisionados e não editáveis na interface (`allowUiUpdates: false`). Para mudar um, edite o JSON e faça o deploy.

Tirar uma integração do `alerting.json` não a apaga: o Grafana a guarda no volume. Para apagar, liste o `uid` dela em `deleteContactPoints`. É assim que sai o e-mail antigo (`atrium-operacao-email`); a exclusão se repete a cada deploy sem erro.

Para testar o contato, abra Alerting, Contact points e clique em View no `atrium-operacao`. A página é só de leitura, mas o botão Test fica ao lado da integração Discord.

A "prontidão" do painel de saúde usa `up{job="atrium-api"}`: a API responde à coleta. A sonda `/ready` do banco não vira métrica.

O alerta "Retenção parada" dispara também sem dados, porque a ausência da série significa que o job nunca rodou.

Um contador que nasce já com valor 1 não gera `increase` na primeira coleta. Um primeiro erro de ingestão logo depois de um deploy pode passar sem alerta.
