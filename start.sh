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

uv run scripts/watch_docs.py &
WATCH_PID=$!
trap 'kill "$WATCH_PID" 2>/dev/null || true' EXIT INT TERM

uv run scripts/serve.py
