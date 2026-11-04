FROM prom/prometheus:v3.5.0

COPY prometheus.yml /etc/prometheus/prometheus.yml

# A Railway injeta o volume em /prometheus. Retenção curta: o painel olha dias, não meses.
ENTRYPOINT ["/bin/prometheus", \
  "--config.file=/etc/prometheus/prometheus.yml", \
  "--storage.tsdb.path=/prometheus", \
  "--storage.tsdb.retention.time=30d", \
  "--enable-feature=expand-environment-variables"]
