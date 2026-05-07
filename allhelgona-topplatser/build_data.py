#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx>=0.27"]
# ///
"""Bygger leaderboarden över allhelgonatändningar 2020-2025 per plats.

Datakällor:
- Bönewebbens öppna API - rooms.results per år (aggregerad ljus-count
  per plats). Inga secrets.
- Geometriska shapefiler (per år, eftersom indelningen ändras över tid):
  - `ls-visualize/data/stift.geojson` - stift (förändras inte i praktiken)
  - `forsamlingsindelning-historik/data/pastorat_{year}.geojson` -
    "ekonomisk enhet" (pastorat eller självständig församling)
  - `forsamlingsindelning-historik/data/forsamlingar_{year}.geojson` -
    församling

Per plats görs point-in-polygon mot stift en gång och mot rätt års
pastorat- och församlings-karta för varje år där platsen hade ljus.

Output: data/leaderboard.json med `per_ar`-mapping per plats. Datat är
historiskt fryst och checkas in - skripten skippar om filen finns.
Kör med --force.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUT = DATA / "leaderboard.json"

REPO_ROOT = ROOT.parent
STIFT_GEOJSON = REPO_ROOT / "ls-visualize" / "data" / "stift.geojson"
HISTORIK_DIR = REPO_ROOT / "forsamlingsindelning-historik" / "data"

BONE = "https://be.svenskakyrkan.se/api"

YEARS = [2020, 2021, 2022, 2023, 2024, 2025]
ROOMS_ROWS = 10000

# Manuella koordinat-fixar för platser där användarna registrerat fel
# i Bönewebben (typiskt 0,0 eller swap av lat/lng). Slug -> (lat, lng).
COORD_OVERRIDES: dict[str, tuple[float, float]] = {
    "umeaaaa_sjukhus":               (63.81759925185444, 20.298219709644773),
    "terra_nova-kyrkan":             (57.61330656398801, 18.31114518147621),
    "karesuando_gamla_kyrkogaaaard": (68.45307210516269, 22.443367825027554),
    "forsa_kyrkogaaaard":            (61.73509569298956, 16.937440530422727),
    "hosjaaoe_kyrkogaaaard":         (60.592306198034855, 15.76170416532879),
    "st_lukas_kyrka_i_skaaoevde":    (58.40421375984256, 13.822435995894448),
}

# Stiftgränsernas polygoner kan klippas på grova kommungränser - en
# kyrka 50 m utanför polygonen ska ändå räknas till stiftet. Vi
# använder point-in-polygon först och faller tillbaka på närmaste
# polygonvertex inom denna marginal när matchen misslyckas. Bara för
# stift; pastorat/församling är så små att samma marginal skulle ge
# fel match.
STIFT_BUFFER_KM = 5.0

# Icke-territoriella församlingar (Karlskrona amiralitet, Tyska
# S:ta Gertrud m.fl.) ligger geografiskt inom en territoriell
# församlings polygon men hör inte dit organisatoriskt. Manuell
# override - slug -> {"forsamling": ..., "pastorat": ...}. Värdena
# ersätter point-in-polygon-resultatet för alla år.
FORSAML_OVERRIDES: dict[str, dict[str, str]] = {
    "amiralitetskyrkan": {
        "forsamling": "Karlskrona amiralitetsförsamling",
        "pastorat":   "Karlskrona amiralitetsförsamling",
    },
    "amiralitetskyrkan_ulrica_pia_i_karlskrona": {
        "forsamling": "Karlskrona amiralitetsförsamling",
        "pastorat":   "Karlskrona amiralitetsförsamling",
    },
    "tyska_kyrkan": {
        "forsamling": "Tyska S:ta Gertruds församling",
        "pastorat":   "Tyska S:ta Gertruds församling",
    },
    "slottskyrkan_stockholm": {
        "forsamling": "Hovförsamlingen",
        "pastorat":   "Hovförsamlingen",
    },
    "finska_kyrkan": {
        "forsamling": "Finska församlingen i Stockholm",
        "pastorat":   "Finska församlingen i Stockholm",
    },
    "christinae_kyrka": {
        "forsamling": "Tyska Christinae församling",
        "pastorat":   "Tyska Christinae församling",
    },
}

# Sveriges grova bbox - används för att upptäcka swappade lat/lng
SE_LAT_LO, SE_LAT_HI = 54.0, 70.0


def normalize_coords(slug: str, lat: float, lng: float) -> tuple[float, float]:
    """Returnerar (lat, lng) efter ev manuell override eller heuristisk
    swap. Triggar bara swap när lat ligger utanför svensk range men lng
    ligger inom - då är värdena uppenbart felregistrerade."""
    if slug in COORD_OVERRIDES:
        return COORD_OVERRIDES[slug]
    if (not (SE_LAT_LO <= lat <= SE_LAT_HI)) and (SE_LAT_LO <= lng <= SE_LAT_HI):
        return lng, lat
    return lat, lng


def point_in_ring(lat: float, lng: float, ring: list) -> bool:
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > lat) != (yj > lat)) and (
            lng < (xj - xi) * (lat - yi) / (yj - yi) + xi
        ):
            inside = not inside
        j = i
    return inside


def point_in_polygon(lat: float, lng: float, polygon: list) -> bool:
    if not polygon or not point_in_ring(lat, lng, polygon[0]):
        return False
    for hole in polygon[1:]:
        if point_in_ring(lat, lng, hole):
            return False
    return True


def lookup_in_features(lat: float, lng: float,
                        features: list[dict], prop: str = "namn") -> str | None:
    for f in features:
        geom = f.get("geometry") or {}
        gtype = geom.get("type")
        coords = geom.get("coordinates") or []
        if gtype == "Polygon":
            if point_in_polygon(lat, lng, coords):
                return f["properties"].get(prop)
        elif gtype == "MultiPolygon":
            for poly in coords:
                if point_in_polygon(lat, lng, poly):
                    return f["properties"].get(prop)
    return None


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def min_distance_to_ring_km(lat: float, lng: float, ring: list) -> float:
    return min(haversine_km(lat, lng, p[1], p[0]) for p in ring)


def lookup_with_buffer(lat: float, lng: float, features: list[dict],
                       buffer_km: float, prop: str = "namn") -> str | None:
    """Som lookup_in_features, men faller tillbaka på närmaste
    polygon-vertex om punkten inte ligger i någon polygon. Används
    för stift där shapefilens gränser kan vara förenklade."""
    name = lookup_in_features(lat, lng, features, prop)
    if name is not None:
        return name
    best = None
    best_d = buffer_km + 0.001
    for f in features:
        geom = f.get("geometry") or {}
        gtype = geom.get("type")
        coords = geom.get("coordinates") or []
        if gtype == "Polygon" and coords:
            d = min_distance_to_ring_km(lat, lng, coords[0])
        elif gtype == "MultiPolygon":
            d = min(
                min_distance_to_ring_km(lat, lng, poly[0])
                for poly in coords if poly
            ) if coords else best_d + 1
        else:
            continue
        if d < best_d:
            best_d = d
            best = f
    return best["properties"].get(prop) if best else None


def fetch_rooms(client: httpx.Client, tag: str) -> list[dict]:
    url = f"{BONE}/geo-positions/tags/{tag}/candles/{ROOMS_ROWS}/0/"
    r = client.get(url)
    r.raise_for_status()
    return r.json()["data"]["rooms"]["results"]


def main() -> None:
    force = "--force" in sys.argv
    if OUT.exists() and not force:
        size_kb = OUT.stat().st_size // 1024
        print(f"{OUT.relative_to(ROOT.parent)} finns redan ({size_kb} KB). "
              f"Kör med --force för att hämta om.", file=sys.stderr)
        return

    if not STIFT_GEOJSON.exists():
        print(f"Saknar stift-geometri: {STIFT_GEOJSON}", file=sys.stderr)
        sys.exit(1)

    DATA.mkdir(parents=True, exist_ok=True)

    print("Läser geometrier ...", file=sys.stderr)
    stifts = json.loads(STIFT_GEOJSON.read_text(encoding="utf-8"))["features"]
    pastorat_per_ar: dict[int, list] = {}
    forsaml_per_ar: dict[int, list] = {}
    for year in YEARS:
        p = HISTORIK_DIR / f"pastorat_{year}.geojson"
        f = HISTORIK_DIR / f"forsamlingar_{year}.geojson"
        if not p.exists() or not f.exists():
            print(f"Saknar geometri för {year}: {p} / {f}", file=sys.stderr)
            sys.exit(1)
        pastorat_per_ar[year] = json.loads(p.read_text(encoding="utf-8"))["features"]
        forsaml_per_ar[year] = json.loads(f.read_text(encoding="utf-8"))["features"]
    print(f"  stift: {len(stifts)}, "
          f"pastorat per år: {[len(pastorat_per_ar[y]) for y in YEARS]}, "
          f"församlingar per år: {[len(forsaml_per_ar[y]) for y in YEARS]}",
          file=sys.stderr)

    kyrkor: dict[str, dict] = {}

    with httpx.Client(timeout=60) as client:
        for year in YEARS:
            tag = f"allhelgona{year}"
            print(f"Hämtar {tag} ...", file=sys.stderr)
            rooms = fetch_rooms(client, tag)
            print(f"  {len(rooms)} rum", file=sys.stderr)

            for room in rooms:
                slug = room["slug"]
                if slug not in kyrkor:
                    raw_lat = float(room["position_lat"])
                    raw_lng = float(room["position_long"])
                    lat, lng = normalize_coords(slug, raw_lat, raw_lng)
                    kyrkor[slug] = {
                        "slug": slug,
                        "name": room["name"],
                        "lat": lat,
                        "lng": lng,
                        "ljus": {},
                    }
                kyrkor[slug]["ljus"][str(year)] = room["count"]

    print("\nKör point-in-polygon ...", file=sys.stderr)
    n_stift = 0
    n_match_year = {y: {"e": 0, "f": 0} for y in YEARS}
    for k in kyrkor.values():
        s = lookup_with_buffer(k["lat"], k["lng"], stifts, STIFT_BUFFER_KM)
        k["stift"] = s
        if s:
            n_stift += 1

        per_ar: dict[str, dict] = {}
        for year_str in k["ljus"].keys():
            year = int(year_str)
            ekon = lookup_in_features(k["lat"], k["lng"], pastorat_per_ar[year])
            forsaml = lookup_in_features(k["lat"], k["lng"], forsaml_per_ar[year])
            per_ar[year_str] = {"e": ekon, "f": forsaml}
            if ekon: n_match_year[year]["e"] += 1
            if forsaml: n_match_year[year]["f"] += 1

        # Icke-territoriella församlingar - override för alla år
        ovr = FORSAML_OVERRIDES.get(k["slug"])
        if ovr:
            for year_str in per_ar:
                per_ar[year_str]["e"] = ovr["pastorat"]
                per_ar[year_str]["f"] = ovr["forsamling"]

        k["per_ar"] = per_ar

    total = len(kyrkor)
    print(f"\nStift-match: {n_stift}/{total} ({n_stift / total * 100:.1f}%)",
          file=sys.stderr)
    for y in YEARS:
        n_year_total = sum(1 for k in kyrkor.values() if str(y) in k["ljus"])
        n_e = n_match_year[y]["e"]
        n_f = n_match_year[y]["f"]
        if n_year_total:
            print(f"  {y}: pastorat {n_e}/{n_year_total} "
                  f"({n_e / n_year_total * 100:.0f}%), "
                  f"församling {n_f}/{n_year_total} "
                  f"({n_f / n_year_total * 100:.0f}%)", file=sys.stderr)

    rows = list(kyrkor.values())
    for k in rows:
        k["total"] = sum(k["ljus"].values())
    rows.sort(key=lambda k: -k["total"])

    payload = {
        "fetched": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "years": YEARS,
        "platser": rows,
    }

    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    kb = OUT.stat().st_size // 1024
    total_ljus = sum(k["total"] for k in rows)
    print(f"\nSkrev {OUT.relative_to(ROOT.parent)} "
          f"({kb} KB, {len(rows)} platser, {total_ljus} ljus totalt)",
          file=sys.stderr)


if __name__ == "__main__":
    main()
