#!/bin/sh
# O Prometheus não expande variáveis de ambiente no arquivo de configuração.
# Troca ${API_HOST}, ${API_PORT} e ${METRICS_TOKEN} antes de iniciar.
set -eu

: "${API_HOST:?API_HOST não definido}"
: "${API_PORT:?API_PORT não definido}"
: "${METRICS_TOKEN:?METRICS_TOKEN não definido}"

sed \
  -e "s|\${API_HOST}|${API_HOST}|g" \
  -e "s|\${API_PORT}|${API_PORT}|g" \
  -e "s|\${METRICS_TOKEN}|${METRICS_TOKEN}|g" \
  /etc/prometheus/prometheus.yml > /tmp/prometheus.yml

exec /bin/prometheus \
  --config.file=/tmp/prometheus.yml \
  --storage.tsdb.path=/prometheus \
  --storage.tsdb.retention.time=30d
