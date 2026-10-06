#!/bin/bash
# Bot de comandos (/status, /casa). O launchd mantém este processo sempre rodando.
set -euo pipefail
cd "$(dirname "$0")"
TELEGRAM_TOKEN="$(security find-generic-password -s monitor-bets-telegram -w)"
export TELEGRAM_TOKEN
export PAINEL_URL="https://igorpiaba.github.io/monitor-bets/"
exec .venv/bin/python -m monitor.bot
