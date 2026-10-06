#!/bin/bash
# Uma rodada do monitor neste Mac, chamada pelo launchd a cada 10 minutos.
# O token do Telegram fica no Chaves (Keychain) do macOS, nunca no repositório.
set -euo pipefail
cd "$(dirname "$0")"
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:$HOME/.local/bin"

# Trava: nunca duas rodadas ao mesmo tempo (agendada + manual). Guarda o PID; se o
# processo dono já morreu (ex.: Mac desligado no meio), a trava velha é ignorada.
mkdir -p .logs
TRAVA=.logs/trava.pid
if [ -f "$TRAVA" ] && kill -0 "$(cat "$TRAVA")" 2>/dev/null; then
  echo "outra rodada em andamento (PID $(cat "$TRAVA")); saindo"
  exit 0
fi
echo $$ > "$TRAVA"
trap 'rm -f "$TRAVA"' EXIT

echo "=== $(date '+%Y-%m-%d %H:%M:%S')"
git pull --rebase -q

TELEGRAM_TOKEN="$(security find-generic-password -s monitor-bets-telegram -w 2>/dev/null || true)"
export TELEGRAM_TOKEN
[ -n "$TELEGRAM_TOKEN" ] || echo "AVISO: token do Telegram não encontrado no Keychain; alertas ficam guardados até ele voltar."
export TELEGRAM_CHAT_ID="-1004471138919"
export PAINEL_URL="https://igorpiaba.github.io/monitor-bets/"

.venv/bin/python -m monitor.rodada

if [ -n "$(git status --porcelain dados/)" ]; then
  git add dados/
  git commit -q -m "atualiza status"
  git push -q
fi
