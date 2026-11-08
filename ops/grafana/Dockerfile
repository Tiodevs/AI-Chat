# O Grafana com os painéis, a fonte de dados e os alertas versionados em ops/grafana. Serve ao
# serviço `grafana` da Railway, que só existe em production (seção 22.1, ADR-009), e ao serviço
# do docker-compose.yml. O contexto de build é esta pasta: na Railway, o diretório raiz do
# serviço é /ops/grafana (seção 22.3). Seção 18.3 do SDD.
FROM grafana/grafana:12.1.0

# O Grafana lê esta pasta ao iniciar e troca `${PROMETHEUS_URL}` e `${DISCORD_WEBHOOK_URL}`
# pelas variáveis do serviço. Sem o webhook, o contato é recusado e o Grafana não sobe.
COPY provisioning/ /etc/grafana/provisioning/
# O caminho que provisioning/dashboards/atrium.yaml aponta.
COPY dashboards/ /etc/grafana/dashboards/
