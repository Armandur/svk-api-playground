#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# ///
"""Hämta alla kyrkor från KBR med identitetRAA + grunddata.

Sparar data/kbr.json:
{
  "fetched_at": "...",
  "count": N,
  "kyrkor": [
    {"id": 32555, "namn": "...", "identitetRAA": "...", "stift": "...",
     "agandeEnhet": "...", "xKoordinat": ..., "yKoordinat": ...}
  ]
}

Kör:
  APIKEY_PROD=... uv run kbr-raa/fetch_kbr.py
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data" / "kbr.json"
API_KEY = os.environ.get("APIKEY_PROD") or os.environ.get("APIKEY")
BASE = "https://api.svenskakyrkan.se/kbr/api/byggnader"
PAGE_SIZE = 100
FIELDS = "id,namn,identitetRAA,stift,agandeEnhet,agandeEnhetLkf,xKoordinat,yKoordinat,nuvarandeAnvandning"


def fetch_page(offset: int) -> list[dict]:
    qs = urllib.parse.urlencode({
        "kyrka": "true",
        "limit": PAGE_SIZE,
        "offset": offset,
        "fields": FIELDS,
        "apikey": API_KEY,
    })
    url = f"{BASE}?{qs}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def main() -> None:
    if not API_KEY:
        sys.exit("APIKEY_PROD eller APIKEY måste vara satt.")

    OUT.parent.mkdir(exist_ok=True)
    all_rows: list[dict] = []
    offset = 0
    while True:
        page = fetch_page(offset)
        if not page:
            break
        all_rows.extend(page)
        print(f"  offset={offset:5d}  +{len(page)} rader  totalt={len(all_rows)}", flush=True)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
        time.sleep(0.1)

    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": len(all_rows),
        "kyrkor": all_rows,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Skrev {OUT.relative_to(ROOT.parent)} ({len(all_rows)} kyrkor)")

    with_raa = sum(1 for r in all_rows if r.get("identitetRAA"))
    print(f"  {with_raa} har identitetRAA, {len(all_rows) - with_raa} saknar")


if __name__ == "__main__":
    main()
