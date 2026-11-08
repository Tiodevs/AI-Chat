# O Prometheus que coleta o /metrics da API. Serve ao serviço `prometheus` da Railway, que só
# existe em production (seção 22.1, ADR-009), e ao serviço do docker-compose.yml. O contexto de
# build é esta pasta: na Railway, o diretório raiz do serviço é /ops/prometheus (seção 22.3).
FROM prom/prometheus:v3.5.0

# A configuração com os marcadores ${...} e o script que os troca antes de iniciar.
COPY prometheus.yml /etc/prometheus/prometheus.yml
COPY entrypoint.sh /entrypoint.sh

# A Railway injeta o volume em /prometheus. Retenção curta: o painel olha dias, não meses.
# O `/bin/sh` roda o script sem precisar do bit de execução, que o arquivo não tem no Git.
ENTRYPOINT ["/bin/sh", "/entrypoint.sh"]
