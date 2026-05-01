#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx>=0.27"]
# ///
"""Hämta en plats från Svenska kyrkans Platser-API och skriv till
place.json bredvid index.html.

Env-vars:
  APIKEY_PROD - SVK-API-nyckel
  PLACE_ID    - UUID för platsen

Körs med cron / systemd-timer typ var 10:e minut.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "place.json"
BASE = "https://api.svenskakyrkan.se/platser/v4"


def main() -> int:
    apikey = os.environ.get("APIKEY_PROD")
    place_id = os.environ.get("PLACE_ID")
    if not apikey or not place_id:
        print("FEL: sätt APIKEY_PROD och PLACE_ID som env-vars", file=sys.stderr)
        return 2

    url = f"{BASE}/place/{place_id}"
    try:
        r = httpx.get(url, params={"apikey": apikey}, timeout=15.0)
    except httpx.HTTPError as e:
        print(f"FEL: nätverksfel mot {url}: {e}", file=sys.stderr)
        return 3

    if r.status_code != 200:
        print(f"FEL: HTTP {r.status_code} från {url}: {r.text[:300]}",
              file=sys.stderr)
        return 4

    place = r.json()
    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "place": place,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"Skrev {OUT.name} ({OUT.stat().st_size // 1024} KB) "
          f"- {place.get('name')!r} ägare {place.get('owner', {}).get('name')!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
