#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyshp>=2.3", "pyproj>=3.6", "shapely>=2.0"]
# ///
"""Identifiera enklaver och exklaver bland Svenska kyrkans församlingar.

- **Exklav:** en del av en församling som ligger åtskild från huvuddelen
  (MultiPolygon med flera del-polygoner; alla utom den största räknas
  som exklaver).
- **Enklav:** en församlings polygon som ligger helt innesluten i en
  *annan* församlings polygon (sällsynt i Sverige men förekommer).

Hämtar shapefile direkt från api.svenskakyrkan.se/kartor/, processar i
minnet och skriver data/enklaver.geojson. Ingen koppling till
forsamlingskarta-leaflet - körs som fristående pilot.

Properties per feature:
  - typ: "enklav" eller "exklav"
  - forsamling: namn på den avvikande församlingen
  - omsluten_av: bara för enklaver, namn på omslutande församling
  - del_index, totalt_delar: bara för exklaver
  - area_km2: grov areal av delen
  - centroid: [lon, lat] för zoom

Kör: uv run forsamlingskarta-enklaver/build_enclaves.py
"""

from __future__ import annotations

import io
import json
import urllib.request
import zipfile
from pathlib import Path

import shapefile
from pyproj import Transformer
from shapely.geometry import MultiPolygon, mapping, shape
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUTPUT = DATA / "enklaver.geojson"
YEAR = "2026-01-01"
URL = f"https://api.svenskakyrkan.se/kartor/forsamlingar_{YEAR}.zip"
# Tolerance i SWEREF-meter. 10 m räcker för UI-visning och bevarar
# topologi - viktigt så att en enklav verkligen "innesluts" av sin
# granne utan glapp eller överlapp efter förenkling.
SIMPLIFY_TOLERANCE_M = 10
# Grövre tolerance för parent-konturen som ritas i UI - vi panorerar
# bara till zoom 10-13 så 100 m räcker. Halverar filstorleken.
PARENT_SIMPLIFY_M = 100


def fetch_shapes() -> list[tuple[str, dict]]:
    """Hämta zip → returnera lista av (namn, geojson-geom-i-WGS84)."""
    print(f"Hämtar {URL}", flush=True)
    with urllib.request.urlopen(URL, timeout=60) as r:
        data = r.read()
    print(f"  → {len(data) // 1024} KB", flush=True)
    zf = zipfile.ZipFile(io.BytesIO(data))
    base = f"forsamlingar_{YEAR}/forsamlingar_{YEAR}"
    sf = shapefile.Reader(
        shp=io.BytesIO(zf.read(f"{base}.shp")),
        shx=io.BytesIO(zf.read(f"{base}.shx")),
        dbf=io.BytesIO(zf.read(f"{base}.dbf")),
        encoding="utf-8",
    )
    transformer = Transformer.from_crs("EPSG:3006", "EPSG:4326", always_xy=True)

    def proj_point(p):
        lon, lat = transformer.transform(p[0], p[1])
        return [lon, lat]

    def proj_ring(ring):
        return [proj_point(p) for p in ring]

    def project(geom: dict) -> dict:
        t = geom["type"]
        if t == "Polygon":
            return {"type": "Polygon",
                    "coordinates": [proj_ring(r) for r in geom["coordinates"]]}
        if t == "MultiPolygon":
            return {"type": "MultiPolygon",
                    "coordinates": [[proj_ring(r) for r in poly]
                                    for poly in geom["coordinates"]]}
        raise ValueError(f"Okänd geometri: {t}")

    rows = []
    for rec in sf.shapeRecords():
        raw = rec.shape.__geo_interface__
        # Simplifiera i SWEREF-meter (innan reprojektion) så att tolerance
        # är jämförbar med fysisk avvikelse på marken.
        s = shape(raw).simplify(SIMPLIFY_TOLERANCE_M, preserve_topology=True)
        projected = project(mapping(s))
        props = rec.record.as_dict()
        rows.append((props.get("namn", "?"), projected))
    print(f"  läste {len(rows)} församlingar", flush=True)
    return rows


def parts_of(geom):
    if isinstance(geom, MultiPolygon):
        return list(geom.geoms)
    return [geom]


def grov_areal_km2(geom) -> float:
    """Approximativ areal i km². Shapely jobbar i WGS84-grader så detta
    är en grov omräkning. På Sveriges latituder: 1° lat ≈ 111 km,
    1° lon ≈ 55 km."""
    return geom.area * 111 * 55


def parent_payload(parent_geom) -> dict:
    """Returnera grov-simplifierad parent-geometri + centroid för UI:t.
    Tolerance i grader: PARENT_SIMPLIFY_M omräknat. På Sveriges latituder
    är 1 grad ≈ 100 km, så 100 m / 100 km = 0.001 grad."""
    deg = PARENT_SIMPLIFY_M / 100_000
    simplified = parent_geom.simplify(deg, preserve_topology=True)
    cx, cy = parent_geom.centroid.x, parent_geom.centroid.y
    return {
        "parent_geom": mapping(simplified),
        "parent_centroid": [round(cx, 5), round(cy, 5)],
    }


def main() -> int:
    DATA.mkdir(exist_ok=True)
    raw_rows = fetch_shapes()
    rows = [(i, name, shape(geom)) for i, (name, geom) in enumerate(raw_rows)]
    output_features = []

    # === Exklaver ===
    exclave_count = 0
    for i, name, s in rows:
        if not isinstance(s, MultiPolygon):
            continue
        sorted_parts = sorted(s.geoms, key=lambda p: p.area, reverse=True)
        # Bygg en lista av ALLA delar i församlingen så UI:t kan rita
        # dem i olika nyanser - vi tar inte ställning till vilken som
        # är "huvuddel" eftersom det kan vara fel (t.ex. när
        # territorialvatten ingår i den största polygonen).
        deg = PARENT_SIMPLIFY_M / 100_000
        alla_delar = []
        for part in sorted_parts:
            simplified = part.simplify(deg, preserve_topology=True)
            cx, cy = part.centroid.x, part.centroid.y
            alla_delar.append({
                "geom": mapping(simplified),
                "area_km2": round(grov_areal_km2(part), 3),
                "centroid": [round(cx, 5), round(cy, 5)],
            })
        for j, part in enumerate(sorted_parts[1:], start=1):
            cx, cy = part.centroid.x, part.centroid.y
            output_features.append({
                "type": "Feature",
                "geometry": mapping(part),
                "properties": {
                    "typ": "exklav",
                    "forsamling": name,
                    "del_index": j,
                    "totalt_delar": len(sorted_parts),
                    "area_km2": round(grov_areal_km2(part), 3),
                    "centroid": [round(cx, 5), round(cy, 5)],
                    "alla_delar": alla_delar,
                },
            })
            exclave_count += 1
    print(f"Hittade {exclave_count} exklaver", flush=True)

    # === Enklaver: del helt innesluten i annan församling ===
    all_parts = []  # (orig_idx, orig_name, part)
    for i, name, s in rows:
        for part in parts_of(s):
            all_parts.append((i, name, part))
    tree = STRtree([p for (_, _, p) in all_parts])

    enclave_count = 0
    for i, name, s in rows:
        for part in parts_of(s):
            for cand_idx in tree.query(part):
                cand_i, cand_name, cand_part = all_parts[cand_idx]
                if cand_i == i:
                    continue
                if cand_part.contains(part):
                    cx, cy = part.centroid.x, part.centroid.y
                    parent = parent_payload(cand_part)
                    output_features.append({
                        "type": "Feature",
                        "geometry": mapping(part),
                        "properties": {
                            "typ": "enklav",
                            "forsamling": name,
                            "omsluten_av": cand_name,
                            "area_km2": round(grov_areal_km2(part), 3),
                            "centroid": [round(cx, 5), round(cy, 5)],
                            "parent_namn": cand_name,
                            "parent_centroid": parent["parent_centroid"],
                            "parent_geom": parent["parent_geom"],
                        },
                    })
                    enclave_count += 1
                    break
    print(f"Hittade {enclave_count} enklaver", flush=True)

    OUTPUT.write_text(
        json.dumps({"type": "FeatureCollection", "features": output_features},
                   separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Skrev {OUTPUT.relative_to(ROOT)} "
          f"({OUTPUT.stat().st_size // 1024} KB, "
          f"{len(output_features)} features)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
