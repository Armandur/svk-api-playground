#!/usr/bin/env bash
# Starta dev-miljön för svk-api-playground:
# - watch_docs.py bygger om docs/svk-apis.html vid ändringar och
#   speglar projektet till /mnt/vmworkspace/svk-api-playground/
# - serve.py listar docs + pilot-projekt på http://localhost:8088/
#
# All output spelas in till dev.log (gitignored) - så Claude kan
# enkelt läsa av runtime-fel efter en testsession.
#
# Ctrl+C avslutar båda processerna.

set -euo pipefail
cd "$(dirname "$0")"

LOG="dev.log"
: > "$LOG"
exec > >(tee -a "$LOG") 2>&1

echo "=== $(date -Is) start.sh ==="

# Ladda API-nycklar från .env om den finns. Variablerna behövs av
# scripts/serve.py för dess SVK-proxy. .env är gitignored.
if [[ -f .env ]]; then
  set -a
  source .env
  set +a
  echo ">> .env laddad (APIKEY_PROD=${APIKEY_PROD:+set}, AZURE_KEY_PROD=${AZURE_KEY_PROD:+set}, CS_SESSION=${CS_SESSION:+set})"
else
  echo ">> ingen .env hittad - SVK-proxyn kommer ge 500"
fi

# Refresh signage-platser/place.json om APIKEY_PROD finns. signage-platser
# läser statisk fil (refresh.py kan annars schemaläggas via cron i prod).
if [[ -f signage-platser/refresh.py && -n "${APIKEY_PROD:-}" ]]; then
  PLACE_ID="${PLACE_ID:-5dab016f-18f3-4973-92d8-69779653a1ef}" \
    uv run signage-platser/refresh.py || echo ">> signage refresh misslyckades (icke-blockerande)"
fi

uv run scripts/watch_docs.py &
WATCH_PID=$!
trap 'kill "$WATCH_PID" 2>/dev/null || true' EXIT INT TERM

uv run scripts/serve.py
