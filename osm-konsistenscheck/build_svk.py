#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Hämtar alla kyrkor och kapell från SVK Platser-API:t (typ
churchAndChapel) och skriver som data/svk_kyrkor.geojson.

Hämtar via dev-proxyn på `http://localhost:8088/api/platser/` så
APIKEY hanteras av servern. Starta `./start.sh` i repo-roten innan
detta körs (eller sätt PLATSER_BASE för annan host/port).

Direktanrop mot api.svenskakyrkan.se gav 500 vid test 2026-05 även med
giltig nyckel - okänd orsak. Proxyn lägger sannolikt på en header som
SVK:s gateway kräver.

Kör: ./start.sh & uv run osm-konsistenscheck/build_svk.py
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data" / "svk_kyrkor.geojson"
BASE = os.environ.get("PLATSER_BASE", "http://localhost:8088/api/platser")
PAGE_SIZE = 500


def fetch_page(offset: int) -> dict:
    qs = urllib.parse.urlencode({
        "is": "churchandchapel",
        "limit": PAGE_SIZE,
        "offset": offset,
    })
    url = f"{BASE}/place?{qs}"
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read())


def main() -> int:

    OUT.parent.mkdir(exist_ok=True)
    all_results: list[dict] = []
    offset = 0
    total_hits = None
    while True:
        data = fetch_page(offset)
        if total_hits is None:
            total_hits = data.get("totalHits", 0)
            print(f"Totalt {total_hits} platser av typ churchAndChapel",
                  flush=True)
        results = data.get("results", [])
        if not results:
            break
        all_results.extend(results)
        print(f"  hämtat {len(all_results)}/{total_hits}", flush=True)
        offset += len(results)
        if offset >= total_hits:
            break
        time.sleep(0.1)

    features = []
    skipped = 0
    for p in all_results:
        # geolocation är en inkapslad GeoJSON-feature, inte rena lon/lat
        coords = (((p.get("geolocation") or {}).get("geometry") or {})
                  .get("coordinates"))
        if not coords or len(coords) != 2:
            skipped += 1
            continue
        lon, lat = coords[0], coords[1]
        owner = p.get("owner") or {}
        contact = p.get("contactInfo") or {}
        visit = p.get("visitingInfo") or {}
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "id": p.get("id"),
                "slug": p.get("slug"),
                "name": p.get("name"),
                "owner_name": owner.get("name"),
                "owner_id": owner.get("id"),
                "owner_type": owner.get("type"),
                "city": visit.get("city"),
                "url": contact.get("url"),
            },
        })

    out = {"type": "FeatureCollection", "features": features}
    OUT.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False),
                   encoding="utf-8")
    print(f"\nSkrev {OUT.relative_to(ROOT)} "
          f"({OUT.stat().st_size // 1024} KB, {len(features)} kyrkor"
          f"{f', {skipped} utan koordinater hoppades över' if skipped else ''})",
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
