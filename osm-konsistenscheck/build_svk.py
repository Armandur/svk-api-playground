#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Hämtar alla kyrkor och kapell från SVK Platser-API:t (typ
churchAndChapel) och skriver som data/svk_kyrkor.geojson.

Direktanrop mot api.svenskakyrkan.se kräver APIKEY (eller APIKEY_PROD)
som env-variabel. Om PLATSER_BASE är satt går vi via den hosten istället
- användbart för att gå via dev-proxyn på localhost:8088 utan att
exponera nyckeln i shell-historik.

Kör:
  APIKEY=... uv run osm-konsistenscheck/build_svk.py
  PLATSER_BASE=http://localhost:8088/api/platser uv run osm-konsistenscheck/build_svk.py
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
DEFAULT_BASE = "https://api.svenskakyrkan.se/platser/v4"
BASE = os.environ.get("PLATSER_BASE", DEFAULT_BASE)
APIKEY = os.environ.get("APIKEY") or os.environ.get("APIKEY_PROD") or ""
PAGE_SIZE = 500
DIRECT_HOST = "api.svenskakyrkan.se"


def fetch_page(offset: int) -> dict:
    params = {
        "is": "churchandchapel",
        "limit": PAGE_SIZE,
        "offset": offset,
    }
    # Direktanrop kräver apikey som query-param. Proxyn lägger på den själv.
    if DIRECT_HOST in BASE:
        if not APIKEY:
            raise SystemExit(
                "Sätt APIKEY (eller APIKEY_PROD) i miljön - eller använd "
                "PLATSER_BASE=http://localhost:8088/api/platser via dev-proxyn.")
        params["apikey"] = APIKEY
    qs = urllib.parse.urlencode(params)
    url = f"{BASE}/place?{qs}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "svk-api-playground/0.1 (rasmus.pettersson.vik@gmail.com)",
    })
    with urllib.request.urlopen(req, timeout=60) as r:
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
        details = p.get("placeDetails") or {}
        access = details.get("accessibility") or {}
        geo_info = p.get("geolocationInfo") or {}
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
                "address": (visit.get("address") or "").strip() or None,
                "postal_code": (visit.get("postalCode") or "").strip() or None,
                "short_description": (p.get("shortDescription") or "").strip() or None,
                "municipality": geo_info.get("municipality") or None,
                "has_toilet": details.get("hasToilet"),
                "has_hearing_loop": access.get("hasHearingLoop"),
                "has_ramp": access.get("hasRamp"),
                "toilet_accessible": access.get("toiletAccessible"),
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
