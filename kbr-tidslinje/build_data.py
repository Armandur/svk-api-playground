# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx", "pyproj"]
# ///
"""
Hämtar alla kyrkor från KBR och konverterar SWEREF99TM → WGS84.
Sparar kbr-tidslinje/data/churches.json.
"""

import json
import os
import sys
from pathlib import Path

import httpx
from pyproj import Transformer

API_KEY = os.environ.get("APIKEY_PROD") or os.environ.get("APIKEY")
if not API_KEY:
    sys.exit("Sätt APIKEY_PROD eller APIKEY i miljön.")

BASE = "https://api.svenskakyrkan.se/kbr/api"
FIELDS = "id,namn,invigning,nybyggnadFran,xKoordinat,yKoordinat,anvandningsfrekvens,skyddEnligtKML,stift,nuvarandeFunktion"
OUT = Path(__file__).parent / "data" / "churches.json"

transformer = Transformer.from_crs("EPSG:3006", "EPSG:4326", always_xy=True)

def sweref_to_wgs84(x, y):
    """SWEREF99TM (x=easting, y=northing) → (lng, lat)."""
    lng, lat = transformer.transform(x, y)
    return round(lat, 6), round(lng, 6)

# Sanitetskontroll mot Storkyrkan i Stockholm (id 36776) - verifierat 0.0 km fel
test_lat, test_lng = sweref_to_wgs84(674691, 6580353)
assert 59.2 < test_lat < 59.4, f"Oväntat lat för Storkyrkan: {test_lat}"
assert 17.9 < test_lng < 18.2, f"Oväntat lng för Storkyrkan: {test_lng}"
print(f"Koordinatkontroll OK: Storkyrkan → {test_lat:.4f}°N, {test_lng:.4f}°E")

churches = []
offset = 0
limit = 100

with httpx.Client(timeout=30) as client:
    while True:
        resp = client.get(
            f"{BASE}/byggnader",
            params={
                "kyrka": "true",
                "limit": limit,
                "offset": offset,
                "fields": FIELDS,
                "apikey": API_KEY,
            },
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break

        for b in batch:
            x, y = b.get("xKoordinat"), b.get("yKoordinat")
            if x is None or y is None:
                continue
            lat, lng = sweref_to_wgs84(x, y)
            churches.append({
                "id":        b["id"],
                "namn":      b["namn"],
                "lat":       lat,
                "lng":       lng,
                "bygg":      b.get("nybyggnadFran"),
                "invigd":    b.get("invigning"),
                "stift":     b.get("stift"),
                "status":    b.get("anvandningsfrekvens"),
                "skydd":     b.get("skyddEnligtKML"),
                "funktion":  b.get("nuvarandeFunktion"),
            })

        print(f"  {offset + len(batch)} / ≥{offset + len(batch)} hämtade", end="\r")
        if len(batch) < limit:
            break
        offset += limit

print(f"\nTotalt: {len(churches)} kyrkor med koordinater")

# Visa årsfördelning
years = [c["bygg"] for c in churches if c["bygg"]]
if years:
    print(f"nybyggnadFran: min={min(years)}, max={max(years)}")
invigd = [c["invigd"] for c in churches if c["invigd"]]
if invigd:
    print(f"invigning:     min={min(invigd)}, max={max(invigd)}")

# Stiftsfördelning
from collections import Counter
for stift, count in sorted(Counter(c["stift"] for c in churches).items(), key=lambda x: -x[1]):
    print(f"  {count:4d}  {stift}")

OUT.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps(churches, ensure_ascii=False, separators=(",", ":")))
print(f"Sparad: {OUT}  ({OUT.stat().st_size // 1024} KB)")
