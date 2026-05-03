#!/usr/bin/env bash
# Hämtar SVK Platser + OSM via Overpass och bygger om diff.geojson.
# Körs manuellt när du vill ha färska siffror i UI:t.
#
#   ./osm-konsistenscheck/rebuild.sh [radius_m]
#
# Default-radie 100 m. SVK-hämtningen går via dev-proxyn (port 8088),
# så ./start.sh måste köra i en annan terminal.

set -euo pipefail
cd "$(dirname "$0")/.."

PORT=8088
if ! curl -fsS -o /dev/null "http://localhost:${PORT}/" 2>/dev/null; then
  echo "FEL: dev-servern svarar inte på http://localhost:${PORT}/" >&2
  echo "Starta den först med ./start.sh i en annan terminal." >&2
  exit 1
fi

echo "=== $(date -Is) rebuild ==="
uv run osm-konsistenscheck/build_svk.py
uv run osm-konsistenscheck/build_kbr.py
uv run osm-konsistenscheck/build_osm.py
uv run osm-konsistenscheck/build_wikidata.py
uv run osm-konsistenscheck/build_diff.py "${1:-100}"
echo "=== klart - ladda om http://ubuntu-ai:${PORT}/osm-konsistenscheck/ ==="
