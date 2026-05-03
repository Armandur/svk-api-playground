#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyproj"]
# ///
"""Hämtar kyrkobyggnader från KBR-API:t och sparar som data/kbr.geojson.
Konverterar SWEREF99TM (EPSG:3006) till WGS84 (EPSG:4326).

Kör:
  APIKEY_PROD=... uv run osm-konsistenscheck/build_kbr.py
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path
from pyproj import Transformer

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data" / "kbr.geojson"
API_KEY = os.environ.get('APIKEY_PROD') or os.environ.get('APIKEY')
BASE_URL = "https://api.svenskakyrkan.se/kbr/api/byggnader"
PAGE_SIZE = 100

def fetch_kbr_page(offset: int) -> list[dict]:
    if not API_KEY:
        raise SystemExit("Sätt APIKEY_PROD eller APIKEY i miljön.")
    
    params = {
        "kyrka": "true",
        "limit": PAGE_SIZE,
        "offset": offset,
        "fields": "id,namn,xKoordinat,yKoordinat,stift,skyddEnligtKML",
        "apikey": API_KEY
    }
    qs = urllib.parse.urlencode(params)
    url = f"{BASE_URL}?{qs}"
    
    req = urllib.request.Request(url, headers={
        "User-Agent": "svk-api-playground/0.1 (rasmus.pettersson.vik@gmail.com)",
    })
    
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

def main() -> int:
    OUT.parent.mkdir(exist_ok=True)
    
    all_buildings: list[dict] = []
    offset = 0
    
    print("Hämtar byggnader från KBR...", flush=True)
    while True:
        try:
            buildings = fetch_kbr_page(offset)
        except Exception as e:
            print(f"Fel vid hämtning (offset {offset}): {e}")
            break
            
        if not buildings:
            break
            
        all_buildings.extend(buildings)
        print(f"  hämtat {len(all_buildings)}...", end="\r", flush=True)
        offset += len(buildings)
        time.sleep(0.1)
    
    print(f"\nTotalt hämtat: {len(all_buildings)}")
    
    # Transformer: EPSG:3006 (SWEREF99TM) -> EPSG:4326 (WGS84)
    # SWEREF99TM: x=Northing, y=Easting. pyproj always_xy=True expects (Easting, Northing)
    transformer = Transformer.from_crs("EPSG:3006", "EPSG:4326", always_xy=True)
    
    features = []
    skipped = 0
    
    for b in all_buildings:
        x = b.get("xKoordinat")
        y = b.get("yKoordinat")
        
        if x is None or y is None:
            skipped += 1
            continue
            
        try:
            # xKoordinat = easting, yKoordinat = northing; always_xy → (lng, lat)
            lng, lat = transformer.transform(x, y)
            
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [lng, lat]
                },
                "properties": {
                    "kbr_id": b.get("id"),
                    "namn": b.get("namn"),
                    "stift": b.get("stift"),
                    "skydd": b.get("skyddEnligtKML")
                }
            })
        except Exception:
            skipped += 1
            
    out = {
        "type": "FeatureCollection",
        "features": features
    }
    
    OUT.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"Skrev {OUT.relative_to(ROOT)} ({len(features)} byggnader, {skipped} hoppades över)")
    
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
