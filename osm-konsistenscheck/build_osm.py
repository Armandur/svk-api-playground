#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Hämtar svenska kristna kyrkor från OpenStreetMap via Overpass API
och skriver som data/osm_kyrkor.geojson.

Filter: amenity=place_of_worship, religion=christian, i Sverige.
Tar med alla kristna samfund - filtreringen mot Svenska kyrkan görs
i diff-steget genom att matcha mot SVK Platser-data geografiskt.

Kör: uv run osm-konsistenscheck/build_osm.py
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data" / "osm_kyrkor.geojson"
# Flera Overpass-instanser - huvudinstansen får ofta 504/429 vid lasttoppar.
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

# Sverige som area. Tar place_of_worship med religion=christian, plus
# building=church (många kyrkbyggnader saknar amenity-taggen). Så
# slipper vi missa kyrkbyggnader som t.ex. Ramsjö kyrka som bara har
# building-taggen i OSM.
QUERY = """
[out:json][timeout:180];
area["ISO3166-1"="SE"][admin_level=2]->.se;
(
  node["amenity"="place_of_worship"]["religion"="christian"](area.se);
  way["amenity"="place_of_worship"]["religion"="christian"](area.se);
  relation["amenity"="place_of_worship"]["religion"="christian"](area.se);
  way["building"="church"](area.se);
  relation["building"="church"](area.se);
  way["building"="chapel"](area.se);
  relation["building"="chapel"](area.se);
);
out tags center;
"""


def _fetch_overpass() -> dict:
    """Försöker varje Overpass-instans i turordning, två gånger var.
    Backoff: 5 s, 15 s mellan försök. Reser sista felet om alla failar."""
    body = urllib.parse.urlencode({"data": QUERY}).encode("utf-8")
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        # Overpass returnerar 406 för default Python-User-Agent,
        # antagligen del av deras anti-abuse-policy.
        "User-Agent": "svk-api-playground/0.1 (rasmus.pettersson.vik@gmail.com)",
    }
    last_err: Exception | None = None
    attempts = [(url, delay) for url in OVERPASS_URLS for delay in (0, 15)]
    for i, (url, delay) in enumerate(attempts, 1):
        if delay:
            print(f"  väntar {delay} s innan retry...", flush=True)
            time.sleep(delay)
        host = url.split("//", 1)[1].split("/", 1)[0]
        print(f"  försök {i}/{len(attempts)}: {host}", flush=True)
        req = urllib.request.Request(url, data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.loads(r.read())
        except HTTPError as e:
            last_err = e
            print(f"    HTTP {e.code} {e.reason}", flush=True)
            # 400 = bad query - meningslöst att retrya andra instanser
            if e.code == 400:
                raise
        except (URLError, TimeoutError, json.JSONDecodeError) as e:
            last_err = e
            print(f"    {type(e).__name__}: {e}", flush=True)
    raise RuntimeError(
        f"Alla Overpass-instanser failade. Senaste fel: {last_err}")


def main() -> int:
    OUT.parent.mkdir(exist_ok=True)
    print("Hämtar OSM-data från Overpass (kan ta 30-60 s)...", flush=True)
    result = _fetch_overpass()

    elements = result.get("elements", [])
    print(f"  hämtade {len(elements)} element", flush=True)

    features = []
    skipped = 0
    for el in elements:
        if el["type"] == "node":
            lon, lat = el.get("lon"), el.get("lat")
        else:
            center = el.get("center") or {}
            lon, lat = center.get("lon"), center.get("lat")
        if lon is None or lat is None:
            skipped += 1
            continue
        tags = el.get("tags", {})
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "osm_id": f"{el['type']}/{el['id']}",
                "name": tags.get("name"),
                "denomination": tags.get("denomination"),
                "religion": tags.get("religion"),
                "wikidata": tags.get("wikidata"),
                "wikipedia": tags.get("wikipedia"),
                "operator": tags.get("operator"),
                "tags": tags,
            },
        })

    out = {"type": "FeatureCollection", "features": features}
    OUT.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False),
                   encoding="utf-8")
    print(f"\nSkrev {OUT.relative_to(ROOT)} "
          f"({OUT.stat().st_size // 1024} KB, {len(features)} OSM-kyrkor"
          f"{f', {skipped} utan koordinater' if skipped else ''})",
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
