FROM prom/prometheus:v3.5.0

COPY prometheus.yml /etc/prometheus/prometheus.yml
COPY entrypoint.sh /entrypoint.sh

# A Railway injeta o volume em /prometheus. Retenção curta: o painel olha dias, não meses.
ENTRYPOINT ["/bin/sh", "/entrypoint.sh"]
