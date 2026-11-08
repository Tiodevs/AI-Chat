#!/usr/bin/env bash
# Instala as CLIs da Railway e da Vercel nas versões fixas do `env` do deploy.yml, com até
# três tentativas (seção 22.3 do SDD).
#
# O postinstall do `@railway/cli` baixa o binário da CLI do GitHub Releases. Esse download às
# vezes fica minutos sem resposta e termina em 504. Foi o que derrubou o job production em
# 2026-11-08, antes de qualquer publicação, e o mesmo endereço respondeu 200 minutos depois.
# Por isso o script tenta de novo: espera 15 segundos depois da primeira falha e 30 depois
# da segunda.
#
# Uso, da raiz do repositório: bash .github/scripts/install-clis.sh
# Lê RAILWAY_CLI_VERSION e VERCEL_CLI_VERSION do ambiente e sai com 1 se as três tentativas
# falharem.
set -euo pipefail

: "${RAILWAY_CLI_VERSION:?defina RAILWAY_CLI_VERSION}"
: "${VERCEL_CLI_VERSION:?defina VERCEL_CLI_VERSION}"

attempts=3
for ((attempt = 1; attempt <= attempts; attempt++)); do
  # Dentro do `if`, uma falha do npm não encerra o script, apesar do `set -e`.
  if npm install --global "@railway/cli@${RAILWAY_CLI_VERSION}" "vercel@${VERCEL_CLI_VERSION}"; then
    exit 0
  fi
  if ((attempt < attempts)); then
    pause=$((attempt * 15))
    # `::warning::` vira um aviso no resumo da execução do GitHub Actions.
    echo "::warning::A instalação das CLIs falhou na tentativa ${attempt} de ${attempts}. Nova tentativa em ${pause} segundos."
    sleep "$pause"
  fi
done

echo "::error::As CLIs da Railway e da Vercel não instalaram depois de ${attempts} tentativas."
exit 1
