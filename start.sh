#!/usr/bin/env bash
# Starta dev-miljön för svk-api-playground:
# - watch_docs.py bygger om docs/svk-apis.html vid ändringar och
#   speglar projektet till /mnt/vmworkspace/svk-api-playground/
# - serve.py listar docs + pilot-projekt på http://localhost:8088/
#
# Ctrl+C avslutar båda.

set -euo pipefail
cd "$(dirname "$0")"

uv run scripts/watch_docs.py &
WATCH_PID=$!
trap 'kill "$WATCH_PID" 2>/dev/null || true' EXIT INT TERM

exec uv run scripts/serve.py
