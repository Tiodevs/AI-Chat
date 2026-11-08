#!/bin/sh
# O Prometheus não expande variáveis de ambiente no arquivo de configuração.
# Troca ${API_HOST}, ${API_PORT} e ${METRICS_TOKEN} antes de iniciar.
#
# Entrada da imagem de ops/prometheus/Dockerfile, na Railway e no docker-compose.yml. Seção 18.3
# do SDD. O .gitattributes mantém este arquivo com quebras LF mesmo no Windows, porque scripts
# executados em contêineres Linux precisam de LF.

# -e para no primeiro erro, e -u trata variável não definida como erro.
set -eu

# Sem uma das três, o serviço não sobe, e o log diz qual falta.
: "${API_HOST:?API_HOST não definido}"
: "${API_PORT:?API_PORT não definido}"
: "${METRICS_TOKEN:?METRICS_TOKEN não definido}"

# A cópia preenchida vai para /tmp; o arquivo da imagem continua com os marcadores. O `|`
# separa as partes do `s`, para uma `/` no valor não quebrar a troca.
sed \
  -e "s|\${API_HOST}|${API_HOST}|g" \
  -e "s|\${API_PORT}|${API_PORT}|g" \
  -e "s|\${METRICS_TOKEN}|${METRICS_TOKEN}|g" \
  /etc/prometheus/prometheus.yml > /tmp/prometheus.yml

# O `exec` deixa o Prometheus no lugar do shell, para ele receber o sinal de parada. Os dados
# ficam no volume de /prometheus, guardados por 30 dias.
exec /bin/prometheus \
  --config.file=/tmp/prometheus.yml \
  --storage.tsdb.path=/prometheus \
  --storage.tsdb.retention.time=30d
