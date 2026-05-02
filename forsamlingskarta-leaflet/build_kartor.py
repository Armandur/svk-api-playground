#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyshp>=2.3", "pyproj>=3.6", "shapely>=2.0"]
# ///
"""Hämtar zip-filer med kartlager från api.svenskakyrkan.se/kartor/,
konverterar shapefile (SWEREF 99 TM) till GeoJSON (WGS84) och skriver
till data/-mappen för Leaflet-användning.

Layers: ekonomiska_enheter, forsamlingar, kontrakt, stift
Years: 2008-2026

Kör utan args för att hämta alla aktuella lager (year=2026):
    uv run forsamlingskarta-leaflet/build_kartor.py

Eller med specifika lager:
    uv run forsamlingskarta-leaflet/build_kartor.py forsamlingar stift
"""

from __future__ import annotations

import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

import shapefile
from pyproj import Transformer
from shapely.geometry import mapping, shape

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DEFAULT_YEAR = "2026-01-01"
DEFAULT_LAYERS = ["forsamlingar", "kontrakt", "stift", "ekonomiska_enheter"]
URL_TPL = "https://api.svenskakyrkan.se/kartor/{layer}_{year}.zip"

# Simplifierings-tolerance per lager, i meter. Sätts till 0 för att
# behålla full detalj. SWEREF 99 TM är i meter så tolerance:n är
# direkt jämförbar med fysisk avvikelse på marken. 10 m motsvarar
# street-level precision - syns inte på normalt zoom-omfång.
SIMPLIFY_TOLERANCE_M = {
    "forsamlingar": 10,         # 1251 polygoner, 23 MB → ~5-7 MB
    "ekonomiska_enheter": 10,
    "kontrakt": 25,             # färre features, kan tåla mer förenkling
    "stift": 50,                # bara 13 stora polygoner
}


def fetch_zip(layer: str, year: str) -> zipfile.ZipFile:
    url = URL_TPL.format(layer=layer, year=year)
    print(f"  hämtar {url}", flush=True)
    with urllib.request.urlopen(url, timeout=60) as r:
        data = r.read()
    print(f"  → {len(data) // 1024} KB", flush=True)
    return zipfile.ZipFile(io.BytesIO(data))


def shapefile_from_zip(zf: zipfile.ZipFile, layer: str, year: str) -> shapefile.Reader:
    base = f"{layer}_{year}/{layer}_{year}"
    return shapefile.Reader(
        shp=io.BytesIO(zf.read(f"{base}.shp")),
        shx=io.BytesIO(zf.read(f"{base}.shx")),
        dbf=io.BytesIO(zf.read(f"{base}.dbf")),
        encoding="utf-8",
    )


def project_geometry(geom: dict, transformer: Transformer) -> dict:
    """Reprojicera GeoJSON-geometri från EPSG:3006 till EPSG:4326.
    Med always_xy=True på transformern är input (x=easting, y=northing)
    och output (lon, lat). GeoJSON-standarden vill ha [lon, lat] så
    vi behåller den ordningen rakt av."""
    def proj_point(p):
        lon, lat = transformer.transform(p[0], p[1])
        return [lon, lat]
    def proj_ring(ring):
        return [proj_point(p) for p in ring]
    t = geom["type"]
    if t == "Polygon":
        return {"type": "Polygon",
                "coordinates": [proj_ring(ring) for ring in geom["coordinates"]]}
    if t == "MultiPolygon":
        return {"type": "MultiPolygon",
                "coordinates": [[proj_ring(ring) for ring in poly]
                                for poly in geom["coordinates"]]}
    if t == "Point":
        return {"type": "Point", "coordinates": proj_point(geom["coordinates"])}
    raise ValueError(f"Okänd geometritype: {t}")


def round_coords(geom: dict, decimals: int = 4) -> dict:
    """Trimma decimaler för mindre filstorlek.
    4 dec ≈ 10 m precision (räcker för nationell visning),
    5 dec ≈ 1 m, 6 dec ≈ 10 cm."""
    def r(p): return [round(c, decimals) for c in p]
    t = geom["type"]
    if t == "Polygon":
        return {"type": "Polygon",
                "coordinates": [[r(p) for p in ring] for ring in geom["coordinates"]]}
    if t == "MultiPolygon":
        return {"type": "MultiPolygon",
                "coordinates": [[[r(p) for p in ring] for ring in poly]
                                for poly in geom["coordinates"]]}
    if t == "Point":
        return {"type": "Point", "coordinates": r(geom["coordinates"])}
    return geom


def simplify_in_meters(geom: dict, tolerance_m: float) -> dict:
    """Douglas-Peucker-simplifiering i SWEREF-meter. Måste köras INNAN
    reprojektion eftersom shapely tolkar tolerance i input-CRS units.
    preserve_topology=True undviker att angränsande församlingar får
    glapp eller överlapp i delade gränser."""
    if tolerance_m <= 0:
        return geom
    s = shape(geom)
    simplified = s.simplify(tolerance_m, preserve_topology=True)
    return mapping(simplified)


def build_geojson(layer: str, year: str, tolerance_m: float) -> dict:
    print(f"[{layer}_{year}] processar (tolerance={tolerance_m} m)…")
    zf = fetch_zip(layer, year)
    sf = shapefile_from_zip(zf, layer, year)
    transformer = Transformer.from_crs("EPSG:3006", "EPSG:4326", always_xy=True)
    features = []
    for shape_rec in sf.shapeRecords():
        geom = shape_rec.shape.__geo_interface__
        # Simplifiera i SWEREF-meter, sen reprojicera
        simplified = simplify_in_meters(geom, tolerance_m)
        projected = project_geometry(simplified, transformer)
        rounded = round_coords(projected)
        props = {k: v for k, v in shape_rec.record.as_dict().items()}
        features.append({"type": "Feature", "properties": props, "geometry": rounded})
    return {"type": "FeatureCollection", "features": features}


def main(argv: list[str]) -> int:
    layers = argv[1:] if len(argv) > 1 else DEFAULT_LAYERS
    DATA.mkdir(exist_ok=True)
    for layer in layers:
        tolerance = SIMPLIFY_TOLERANCE_M.get(layer, 10)
        gj = build_geojson(layer, DEFAULT_YEAR, tolerance)
        out = DATA / f"{layer}.geojson"
        out.write_text(json.dumps(gj, separators=(",", ":"), ensure_ascii=False),
                       encoding="utf-8")
        print(f"  skrev {out.relative_to(ROOT)} "
              f"({out.stat().st_size // 1024} KB, {len(gj['features'])} features)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
