#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyshp>=2.3", "pyproj>=3.6", "shapely>=2.0"]
# ///
"""Hämtar Svenska kyrkans pastorat- och församlingsindelning för åren
2008-2026 (lagren `ekonomiska_enheter` resp `forsamlingar`), simplifierar
till GeoJSON och beräknar mappning pastorat → ingående församlingar
samt summary.json med strukturella förändringar mellan år.

Output:
  data/pastorat_<år>.geojson      (en per år, ekonomiska_enheter)
  data/forsamlingar_<år>.geojson  (en per år)
  data/summary.json               (förändringar år för år)

Termen "pastorat" här avser ekonomiska enheter, vilket inkluderar både
pastorat (flera församlingar med gemensam ekonomi) och självständiga
församlingar med egen ekonomi.

Kör: uv run forsamlingsindelning-historik/build_historik.py
"""

from __future__ import annotations

import io
import json
import re
import sys
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path

import shapefile
from pyproj import Transformer
from shapely.geometry import mapping, shape
from shapely.ops import unary_union
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
URL_TPL = "https://api.svenskakyrkan.se/kartor/{layer}_{year}-01-01.zip"
DEFAULT_YEARS = list(range(2008, 2027))
SIMPLIFY_TOLERANCE_M = 100


def fetch_zip(layer: str, year: int) -> zipfile.ZipFile:
    url = URL_TPL.format(layer=layer, year=year)
    print(f"  hämtar {url}", flush=True)
    with urllib.request.urlopen(url, timeout=120) as r:
        return zipfile.ZipFile(io.BytesIO(r.read()))


def open_shapefile(zf: zipfile.ZipFile, layer: str, year: int) -> shapefile.Reader:
    stem = f"{layer}_{year}-01-01"
    candidates = [stem, f"{stem}/{stem}"]
    base = next((c for c in candidates if f"{c}.shp" in zf.namelist()), None)
    if base is None:
        raise RuntimeError(f"Hittar inte .shp för {layer}_{year}")
    return shapefile.Reader(
        shp=io.BytesIO(zf.read(f"{base}.shp")),
        shx=io.BytesIO(zf.read(f"{base}.shx")),
        dbf=io.BytesIO(zf.read(f"{base}.dbf")),
        encoding="utf-8",
    )


def project_geom(transformer: Transformer):
    def proj_point(p):
        lon, lat = transformer.transform(p[0], p[1])
        return [round(lon, 4), round(lat, 4)]

    def proj_ring(r):
        return [proj_point(p) for p in r]

    def project(geom):
        t = geom["type"]
        if t == "Polygon":
            return {"type": "Polygon",
                    "coordinates": [proj_ring(r) for r in geom["coordinates"]]}
        if t == "MultiPolygon":
            return {"type": "MultiPolygon",
                    "coordinates": [[proj_ring(r) for r in poly]
                                    for poly in geom["coordinates"]]}
        raise ValueError(t)
    return project


CODE_FIELD = {
    "forsamlingar": "lkfkod",
    "ekonomiska_enheter": "skpkod",
    "kontrakt": "kkkod",
    "stift": "skod",
}


def process_layer(layer: str, year: int) -> dict:
    """Returnera GeoJSON med en feature per unik kod (aggregerad)."""
    zf = fetch_zip(layer, year)
    sf = open_shapefile(zf, layer, year)
    transformer = Transformer.from_crs("EPSG:3006", "EPSG:4326", always_xy=True)
    project = project_geom(transformer)
    code_field = CODE_FIELD.get(layer, "lkfkod")

    groups: dict[str, list] = defaultdict(list)
    namn_per_kod: dict[str, str] = {}
    for rec in sf.shapeRecords():
        raw = rec.shape.__geo_interface__
        s = shape(raw).simplify(SIMPLIFY_TOLERANCE_M, preserve_topology=True)
        props = rec.record.as_dict()
        code = props.get(code_field, "") or "?"
        groups[code].append(s)
        namn_per_kod.setdefault(code, props.get("namn", "?"))

    features = []
    for code, geoms in groups.items():
        merged = unary_union(geoms) if len(geoms) > 1 else geoms[0]
        features.append({
            "type": "Feature",
            "geometry": project(mapping(merged)),
            "properties": {
                "namn": namn_per_kod[code],
                "kod": code,
            },
        })
    return {"type": "FeatureCollection", "features": features}


def map_forsamlingar_till_pastorat(
    pastorat_gj: dict, forsamlingar_gj: dict
) -> dict[str, list[str]]:
    """Mappa varje församling till sitt pastorat via centroid-inneslutning.
    Returnera: {pastorat_lkfkod: [forsamling_lkfkod, ...]}"""
    pastorat_shapes = [shape(f["geometry"]) for f in pastorat_gj["features"]]
    pastorat_kod = [f["properties"]["kod"] for f in pastorat_gj["features"]]
    tree = STRtree(pastorat_shapes)
    mapping_dict: dict[str, list[str]] = {k: [] for k in pastorat_kod}
    for f in forsamlingar_gj["features"]:
        s = shape(f["geometry"])
        c = s.centroid
        for idx in tree.query(c):
            if pastorat_shapes[idx].contains(c):
                mapping_dict[pastorat_kod[idx]].append(f["properties"]["kod"])
                break
    return mapping_dict


_GENITIV_RE = re.compile(r"s\b(?= (?:församling|pastorat|kyrkliga))")
# Bara "församling" tas bort vid strip_suffix - "pastorat" och
# "kyrkliga samfällighet" är distinkta typer som ska behållas så att
# terminologi-byten (t.ex. "X kyrkliga samfällighet" → "X pastorat")
# inte filtreras bort.
_SUFFIX_RE = re.compile(r"\s+församling$", re.IGNORECASE)


def _normalize_namn(s: str, strip_suffix: bool = False) -> str:
    """Tar bort genitiv-s före 'församling/pastorat/kyrkliga' så att
    inkonsekvent stavning ('Tierp församling' vs 'Tierps församling')
    inte räknas som namnbyte. Med strip_suffix=True tas även suffixet
    'församling' bort så att 'Bromma' jämställs med 'Bromma församling'
    (2015-reformen). Pastorat/samfällighet-suffix bibehålls."""
    s = _GENITIV_RE.sub("", s)
    if strip_suffix:
        s = _SUFFIX_RE.sub("", s).strip()
    return s


def _namn_equiv(a: str, b: str, strip_suffix: bool = False) -> bool:
    return _normalize_namn(a, strip_suffix) == _normalize_namn(b, strip_suffix)


def _typ_av_namn(s: str) -> str:
    """Klassificera en ekonomisk-enhets-namnsträng som pastorat,
    forsamling eller annat. "Kyrklig(a) samfällighet(er)" är dåtidens
    samarbetsform, motsvarar dagens pastorat. SVK gick över till
    pastorat-terminologin runt 2009-2014."""
    s = s.lower()
    if "pastorat" in s or "samfällighet" in s:
        return "pastorat"
    if "församling" in s:
        return "forsamling"
    return "annat"


def _classify_namnbyte(fran: str, till: str) -> str:
    """Avgör vilken slags ändring ett namnbyte representerar.
    Bakgrund: SVK återanvänder samma skpkod när en församling med egen
    ekonomi (= "enförsamlingspastorat") utökas till ett flerförsamlings-
    pastorat. Då ser det ut som "X församling → Y pastorat" på samma kod
    fast det egentligen är en pastoratsbildning."""
    f_typ, t_typ = _typ_av_namn(fran), _typ_av_namn(till)
    if f_typ == "forsamling" and t_typ == "pastorat":
        return "pastoratsbildning"
    if f_typ == "pastorat" and t_typ == "forsamling":
        return "pastoratsupplosning"
    return "namnbyte"


def diff_year(prev: dict, curr: dict) -> dict:
    """Beräkna förändringar mellan två år. Båda dicts har:
       {namn: {kod: namn}, mapping: {pastorat_kod: [forsamling_kod...]}}"""
    p_namn, c_namn = prev["pastorat_namn"], curr["pastorat_namn"]
    p_map, c_map = prev["pastorat_map"], curr["pastorat_map"]
    f_namn_prev, f_namn_curr = prev["forsamling_namn"], curr["forsamling_namn"]

    # Pastorat
    nya_pastorat_kod = sorted(c_namn.keys() - p_namn.keys())
    forsvunna_pastorat_kod = sorted(p_namn.keys() - c_namn.keys())
    nya_pastorat = [
        {
            "kod": k,
            "namn": c_namn[k],
            "ingaende": sorted(
                f_namn_curr.get(fk, fk) for fk in c_map.get(k, [])
            ),
        }
        for k in nya_pastorat_kod
    ]
    forsvunna_pastorat = []
    forsvunna_fore = []  # församlingar med egen ekonomi som upphör
    for k in forsvunna_pastorat_kod:
        ingaende = sorted(f_namn_prev.get(fk, fk) for fk in p_map.get(k, []))
        item = {"kod": k, "namn": p_namn[k], "ingaende": ingaende}
        # FörE har 1 ingående församling och namnet innehåller "församling"
        # (utan "pastorat"/"samfällighet"). Andra fall är riktigt upplösta
        # flerförsamlings-pastorat.
        if len(ingaende) <= 1 and _typ_av_namn(p_namn[k]) == "forsamling":
            forsvunna_fore.append(item)
        else:
            forsvunna_pastorat.append(item)
    # Dela upp namnändringar i bildning/upplösning/rent namnbyte.
    # Hoppa över ändringar som bara är genitiv-s-skillnader (ej riktig
    # förändring, bara datakvalitet).
    namnbyte_pastorat = []
    pastoratsbildning = []
    pastoratsupplosning = []
    for k in p_namn.keys() & c_namn.keys():
        if p_namn[k] == c_namn[k]:
            continue
        if _namn_equiv(p_namn[k], c_namn[k]):
            continue
        cat = _classify_namnbyte(p_namn[k], c_namn[k])
        item = {"kod": k, "fran": p_namn[k], "till": c_namn[k]}
        if cat == "pastoratsbildning":
            item["ingaende"] = sorted(
                f_namn_curr.get(fk, fk) for fk in c_map.get(k, [])
            )
            pastoratsbildning.append(item)
        elif cat == "pastoratsupplosning":
            item["ingaende"] = sorted(
                f_namn_prev.get(fk, fk) for fk in p_map.get(k, [])
            )
            pastoratsupplosning.append(item)
        else:
            # Rent namnbyte: filtrera bort fall som bara är suffix-
            # tillägg ('X' → 'X församling' efter 2015-reformen).
            if _namn_equiv(p_namn[k], c_namn[k], strip_suffix=True):
                continue
            namnbyte_pastorat.append(item)
    namnbyte_pastorat.sort(key=lambda x: x["till"])
    pastoratsbildning.sort(key=lambda x: x["till"])
    pastoratsupplosning.sort(key=lambda x: x["fran"])

    # Sammansättningsändring: samma kod, andra ingående församlingar.
    # Hoppa över de som redan klassats som bildning/upplösning eftersom
    # ingående-listan redan beskriver vad som är aktuellt nu.
    omklassade_koder = {x["kod"] for x in pastoratsbildning + pastoratsupplosning}
    sammansattning = []
    for k in p_namn.keys() & c_namn.keys():
        if k in omklassade_koder:
            continue
        prev_set = set(p_map.get(k, []))
        curr_set = set(c_map.get(k, []))
        if prev_set != curr_set:
            sammansattning.append({
                "kod": k,
                "namn": c_namn[k],
                "tillagda": sorted(
                    f_namn_curr.get(fk, fk) for fk in curr_set - prev_set
                ),
                "fjarnade": sorted(
                    f_namn_prev.get(fk, fk) for fk in prev_set - curr_set
                ),
            })
    sammansattning.sort(key=lambda x: x["namn"])

    # Församlingar (sekundär info)
    nya_forsamlingar = sorted(
        f"{f_namn_curr[k]} ({k})" for k in f_namn_curr.keys() - f_namn_prev.keys()
    )
    forsvunna_forsamlingar = sorted(
        f"{f_namn_prev[k]} ({k})" for k in f_namn_prev.keys() - f_namn_curr.keys()
    )
    namnbyte_forsamlingar = sorted(
        f"{f_namn_prev[k]} → {f_namn_curr[k]} ({k})"
        for k in f_namn_prev.keys() & f_namn_curr.keys()
        if f_namn_prev[k] != f_namn_curr[k]
        and not _namn_equiv(f_namn_prev[k], f_namn_curr[k], strip_suffix=True)
    )

    return {
        "pastorat": {
            "nya": nya_pastorat,
            "forsvunna": forsvunna_pastorat,
            "forsvunna_fore": forsvunna_fore,
            "namnbyte": namnbyte_pastorat,
            "pastoratsbildning": pastoratsbildning,
            "pastoratsupplosning": pastoratsupplosning,
            "sammansattning": sammansattning,
        },
        "forsamlingar": {
            "nya": nya_forsamlingar,
            "forsvunna": forsvunna_forsamlingar,
            "namnbyte": namnbyte_forsamlingar,
        },
    }


def load_year_from_disk(year: int) -> dict | None:
    p_path = DATA / f"pastorat_{year}.geojson"
    f_path = DATA / f"forsamlingar_{year}.geojson"
    if not (p_path.exists() and f_path.exists()):
        return None
    pg = json.loads(p_path.read_text(encoding="utf-8"))
    fg = json.loads(f_path.read_text(encoding="utf-8"))
    return {
        "pastorat_namn": {f["properties"]["kod"]: f["properties"]["namn"]
                          for f in pg["features"]},
        "pastorat_map": {
            f["properties"]["kod"]: f["properties"].get("forsamlingar_kod", [])
            for f in pg["features"]
        },
        "forsamling_namn": {f["properties"]["kod"]: f["properties"]["namn"]
                            for f in fg["features"]},
    }


def main(argv: list[str]) -> int:
    args = argv[1:]
    rebuild_summary_only = "--rebuild-summary" in args
    args = [a for a in args if a != "--rebuild-summary"]
    years = [int(y) for y in args] if args else DEFAULT_YEARS
    DATA.mkdir(exist_ok=True)
    state_per_ar: dict[int, dict] = {}

    if rebuild_summary_only:
        print("Bygger om summary.json från befintliga geojson-filer", flush=True)
        for year in years:
            state = load_year_from_disk(year)
            if state is None:
                print(f"  saknar data för {year}, hoppar över", flush=True)
                continue
            state_per_ar[year] = state
            print(f"  läste {year}: {len(state['pastorat_namn'])} pastorat / "
                  f"{len(state['forsamling_namn'])} församlingar", flush=True)
    else:
      for year in years:
        print(f"[{year}]", flush=True)
        pastorat_gj = process_layer("ekonomiska_enheter", year)
        forsamlingar_gj = process_layer("forsamlingar", year)

        pastorat_map = map_forsamlingar_till_pastorat(pastorat_gj, forsamlingar_gj)

        # Lägg till ingående församlingar i pastorat-properties
        for f in pastorat_gj["features"]:
            kod = f["properties"]["kod"]
            f["properties"]["forsamlingar_kod"] = pastorat_map.get(kod, [])
            f["properties"]["antal_forsamlingar"] = len(pastorat_map.get(kod, []))

        (DATA / f"pastorat_{year}.geojson").write_text(
            json.dumps(pastorat_gj, separators=(",", ":"), ensure_ascii=False),
            encoding="utf-8")
        (DATA / f"forsamlingar_{year}.geojson").write_text(
            json.dumps(forsamlingar_gj, separators=(",", ":"), ensure_ascii=False),
            encoding="utf-8")

        state_per_ar[year] = {
            "pastorat_namn": {f["properties"]["kod"]: f["properties"]["namn"]
                              for f in pastorat_gj["features"]},
            "pastorat_map": pastorat_map,
            "forsamling_namn": {f["properties"]["kod"]: f["properties"]["namn"]
                                for f in forsamlingar_gj["features"]},
        }
        print(f"  → {len(pastorat_gj['features'])} pastorat / "
              f"{len(forsamlingar_gj['features'])} församlingar", flush=True)

    # Förändringar mellan på varandra följande år
    sorted_years = sorted(state_per_ar.keys())
    forandringar = {}
    for prev_y, curr_y in zip(sorted_years, sorted_years[1:]):
        d = diff_year(state_per_ar[prev_y], state_per_ar[curr_y])
        if any(d["pastorat"].values()) or any(d["forsamlingar"].values()):
            forandringar[f"{prev_y}-{curr_y}"] = d

    summary = {
        "ar": sorted_years,
        "antal_pastorat_per_ar": {
            str(y): len(state_per_ar[y]["pastorat_namn"]) for y in sorted_years},
        "antal_forsamlingar_per_ar": {
            str(y): len(state_per_ar[y]["forsamling_namn"]) for y in sorted_years},
        "forandringar": forandringar,
    }
    (DATA / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSammanfattning skriven till summary.json", flush=True)
    print(f"Pastorat: {len(state_per_ar[sorted_years[0]]['pastorat_namn'])} "
          f"({sorted_years[0]}) → "
          f"{len(state_per_ar[sorted_years[-1]]['pastorat_namn'])} "
          f"({sorted_years[-1]})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
