# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx", "pyproj", "python-dotenv"]
# ///
"""
Jämför KBR-koordinater mot SVK Platser-API:t och OSM (Overpass).
Kör även ett brett utbud av datakvalitetskontroller på KBR-data.

Matchning: normaliserat namn + geografiskt närmaste kandidat (cap 200 km).

Skriver:
  data/report.json   - koordinatjämförelse KBR vs Platser/OSM
  data/quality.json  - kategoriserade kvalitetsproblem
  data/stats.json    - sammanfattande statistik
  data/report.csv    - koordinatavvikelser >= MIN_AVSTAND_M

  data/raw/          - cachad rådata per källa (TTL-styrd)
  data/snapshots/YYYY-MM-DD/  - daglig gzip-snapshot av report + quality

Kör:
  APIKEY_PROD=<nyckel> uv run kbr-kvalitet/build_report.py
  APIKEY_PROD=<nyckel> uv run kbr-kvalitet/build_report.py --no-fetch
  APIKEY_PROD=<nyckel> uv run kbr-kvalitet/build_report.py --refresh=kbr,osm

Flaggor:
  --no-fetch          Använd cachen, hämta inte ny data (fel om cache saknas)
  --refresh=SRC[,SRC] Tvinga omladdning för angivna källor:
                      kbr, kbr_begravning, platser, platser_extra, osm
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
from matching import MAX_MATCH_M, closest_match, haversine, normalize, sweref_to_wgs84  # noqa: E402
from quality import run_all_checks  # noqa: E402

load_dotenv(Path(__file__).parent.parent / ".env")

API_KEY = os.environ.get("APIKEY_PROD") or os.environ.get("APIKEY")
if not API_KEY:
    sys.exit("Sätt APIKEY_PROD eller APIKEY i miljön.")

ap = argparse.ArgumentParser()
ap.add_argument("--no-fetch", action="store_true")
ap.add_argument("--refresh", default="")
args    = ap.parse_args()
NO_FETCH = args.no_fetch
REFRESH  = {s.strip() for s in args.refresh.split(",") if s.strip()}

KBR_BASE      = "https://api.svenskakyrkan.se/kbr/api"
PLATSER_BASE  = "https://api.svenskakyrkan.se/platser/v4"
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
OVERPASS_QUERY = """
[out:json][timeout:180];
area["ISO3166-1"="SE"][admin_level=2]->.se;
(
  node["amenity"="place_of_worship"]["religion"="christian"]["name"](area.se);
  way["amenity"="place_of_worship"]["religion"="christian"]["name"](area.se);
  relation["amenity"="place_of_worship"]["religion"="christian"]["name"](area.se);
  way["building"="church"]["name"](area.se);
  way["building"="chapel"]["name"](area.se);
  way["landuse"="cemetery"]["name"](area.se);
  relation["landuse"="cemetery"]["name"](area.se);
  node["amenity"="grave_yard"]["name"](area.se);
  node["amenity"="crematorium"]["name"](area.se);
  way["amenity"="crematorium"]["name"](area.se);
  node["man_made"="campanile"]["name"](area.se);
  way["man_made"="campanile"]["name"](area.se);
);
out tags center;
"""

OUT_DIR       = Path(__file__).parent / "data"
RAW_DIR       = OUT_DIR / "raw"
MIN_AVSTAND_M = 200
LANG_BYGG     = 300    # år

OUT_DIR.mkdir(exist_ok=True)
RAW_DIR.mkdir(parents=True, exist_ok=True)

FIELDS = (
    "id,namn,facilityPartId,xKoordinat,yKoordinat,stift,lan,"
    "nuvarandeFunktion,skyddEnligtKML,nybyggnadFran,invigning,"
    "identitetRAA,byggarea,fastighetsbeteckning,planform,"
    "materialStomme,materialFasad,"
    "anvandningsfrekvens,nuvarandeAnvandning,ursprungligAnvandning,"
    "handlingsprogramTillganglighet,tillganglighetsanpassning,"
    "agandeEnhet,agandeEnhetLkf,geografiskEnhet,geografiskEnhetLkf,"
    "andradDatum,skapadDatum"
)

# -------------------------------------------------------------------------
# Cache-hjälpare
# -------------------------------------------------------------------------

def fetch_or_cache(name: str, ttl_hours: float, fetcher_fn) -> list[dict]:
    cache_file = RAW_DIR / f"{name}.json"
    meta_file  = RAW_DIR / "_metadata.json"

    meta: dict[str, str] = {}
    if meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    def _load_cache() -> list[dict]:
        if not cache_file.exists():
            sys.exit(f"Cache saknas för '{name}': kör utan --no-fetch först.")
        return json.loads(cache_file.read_text(encoding="utf-8"))

    def _save(data: list[dict]) -> list[dict]:
        cache_file.write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8")
        meta[name] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return data

    if NO_FETCH and name not in REFRESH:
        print(f"  [{name}] laddar från cache", flush=True)
        return _load_cache()

    if name not in REFRESH and cache_file.exists() and name in meta:
        ts = datetime.fromisoformat(meta[name])
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age_h = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
        if age_h < ttl_hours:
            print(f"  [{name}] cache {age_h:.1f}h gammal, hoppar fetch", flush=True)
            return _load_cache()

    try:
        data = fetcher_fn()
    except Exception as e:
        if cache_file.exists():
            print(f"  [{name}] fetch misslyckades ({e}), använder gammal cache", flush=True)
            return _load_cache()
        raise
    return _save(data)


# -------------------------------------------------------------------------
# Hämtningsfunktioner
# -------------------------------------------------------------------------

def _fetch_kbr_raw() -> list[dict]:
    result: list[dict] = []
    offset = 0
    with httpx.Client(timeout=30) as client:
        while True:
            resp = client.get(
                f"{KBR_BASE}/byggnader",
                params={"kyrka": "true", "limit": 100, "offset": offset,
                        "fields": FIELDS, "apikey": API_KEY},
            )
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            for b in batch:
                if b.get("xKoordinat") is not None and b.get("yKoordinat") is not None:
                    result.append(b)
            print(f"    KBR: {len(result)} hämtade", end="\r", flush=True)
            if len(batch) < 100:
                break
            offset += 100
    print(f"\n    KBR klar: {len(result)} kyrkor", flush=True)
    return result


def _fetch_kbr_begravningsplatser() -> list[dict]:
    result: list[dict] = []
    offset = 0
    with httpx.Client(timeout=30) as client:
        while True:
            resp = client.get(
                f"{KBR_BASE}/begravningsplatser",
                params={"limit": 100, "offset": offset,
                        "fields": "id,namn,stift,xKoordinat,yKoordinat", "apikey": API_KEY},
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
                result.append({
                    "kbr_id": b["id"], "namn": b["namn"],
                    "stift": b.get("stift", ""),
                    "kbr_lat": lat, "kbr_lng": lng,
                })
            print(f"    KBR Begravningsplatser: {len(result)}", end="\r", flush=True)
            if len(batch) < 100:
                break
            offset += 100
    print(f"\n    KBR Begravningsplatser klar: {len(result)}", flush=True)
    return result


def _fetch_platser() -> list[dict]:
    result: list[dict] = []
    offset, total_hits = 0, None
    while True:
        qs  = urllib.parse.urlencode({"is": "churchandchapel", "limit": 500,
                                       "offset": offset, "apikey": API_KEY})
        req = urllib.request.Request(
            f"{PLATSER_BASE}/place?{qs}",
            headers={"User-Agent": "svk-api-playground/0.1 (rasmus.pettersson.vik@gmail.com)"},
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
        if total_hits is None:
            total_hits = data.get("totalHits", 0)
        results = data.get("results", [])
        if not results:
            break
        for p in results:
            coords = (((p.get("geolocation") or {}).get("geometry") or {}).get("coordinates"))
            if not coords or len(coords) != 2:
                continue
            result.append({"platser_id": p.get("id"), "namn": p.get("name", ""),
                            "platser_slug": p.get("slug", ""),
                            "platser_lat": round(coords[1], 6),
                            "platser_lng": round(coords[0], 6)})
        offset += len(results)
        print(f"    Platser: {len(result)}/{total_hits}", end="\r", flush=True)
        if offset >= total_hits:
            break
        time.sleep(0.05)
    print(f"\n    Platser klar: {len(result)} kyrkor", flush=True)
    return result


def _fetch_platser_extra() -> list[dict]:
    result: list[dict] = []
    for _platstyp in ("parishhome", "cemetery", "secretariat"):
        _offset_p, _total_p = 0, None
        while True:
            qs = urllib.parse.urlencode({"is": _platstyp, "limit": 500,
                                         "offset": _offset_p, "apikey": API_KEY})
            req = urllib.request.Request(
                f"{PLATSER_BASE}/place?{qs}",
                headers={"User-Agent": "svk-api-playground/0.1 (rasmus.pettersson.vik@gmail.com)"},
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                _data = json.loads(r.read())
            if _total_p is None:
                _total_p = _data.get("totalHits", 0)
            _results = _data.get("results", [])
            if not _results:
                break
            for p in _results:
                coords = (((p.get("geolocation") or {}).get("geometry") or {}).get("coordinates"))
                if not coords or len(coords) != 2:
                    continue
                result.append({
                    "platser_id": p.get("id"), "namn": p.get("name", ""),
                    "platser_slug": p.get("slug", ""),
                    "platser_lat": round(coords[1], 6), "platser_lng": round(coords[0], 6),
                    "platser_typ": _platstyp,
                })
            _offset_p += len(_results)
            n = sum(1 for x in result if x["platser_typ"] == _platstyp)
            print(f"    Platser {_platstyp}: {n}/{_total_p}", end="\r", flush=True)
            if _offset_p >= _total_p:
                break
            time.sleep(0.05)
    print(f"\n    Platser övriga klar: {len(result)} totalt", flush=True)
    return result


def _fetch_osm() -> list[dict]:
    result: list[dict] = []
    body = urllib.parse.urlencode({"data": OVERPASS_QUERY}).encode("utf-8")
    hdrs = {"Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "svk-api-playground/0.1 (rasmus.pettersson.vik@gmail.com)"}
    ok = False
    for url in OVERPASS_URLS:
        for attempt in range(2):
            try:
                req = urllib.request.Request(url, data=body, headers=hdrs)
                with urllib.request.urlopen(req, timeout=200) as r:
                    osm_data = json.loads(r.read())
                for el in osm_data.get("elements", []):
                    name = (el.get("tags") or {}).get("name")
                    if not name:
                        continue
                    if el["type"] == "node":
                        ola, olo = el["lat"], el["lon"]
                    elif "center" in el:
                        ola, olo = el["center"]["lat"], el["center"]["lon"]
                    else:
                        continue
                    tags = el.get("tags") or {}
                    is_cemetery    = (tags.get("landuse") == "cemetery"
                                      or tags.get("amenity") == "grave_yard")
                    is_crematorium = tags.get("amenity") == "crematorium"
                    is_campanile   = tags.get("man_made") == "campanile"
                    if is_cemetery:
                        osm_typ = "begravningsplats"
                    elif is_crematorium:
                        osm_typ = "krematorium"
                    elif is_campanile:
                        osm_typ = "klockstapel"
                    else:
                        osm_typ = "kyrka"
                    result.append({"osm_id": el["id"], "namn": name,
                                    "osm_lat": round(ola, 6), "osm_lng": round(olo, 6),
                                    "osm_typ": osm_typ})
                ok = True
                break
            except Exception as e:
                print(f"    Overpass {url} fel: {e}", flush=True)
                time.sleep(15 if attempt == 0 else 0)
        if ok:
            break
    if not ok:
        raise RuntimeError("Alla Overpass-servrar misslyckades")
    print(f"    OSM klar: {len(result)} platser", flush=True)
    return result


# -------------------------------------------------------------------------
# Hämta / ladda data
# -------------------------------------------------------------------------

print("=== Hämtar data ===", flush=True)

kbr_churches_raw       = fetch_or_cache("kbr_raw",        24, _fetch_kbr_raw)
kbr_begravningsplatser = fetch_or_cache("kbr_begravning", 24, _fetch_kbr_begravningsplatser)
platser_list           = fetch_or_cache("platser",        24, _fetch_platser)
platser_extra_list     = fetch_or_cache("platser_extra",  24, _fetch_platser_extra)
osm_list               = fetch_or_cache("osm",             6, _fetch_osm)

# Bygg stripped kbr_churches från rådata (konverterar SWEREF -> WGS84)
kbr_churches: list[dict] = []
for b in kbr_churches_raw:
    x, y = b.get("xKoordinat"), b.get("yKoordinat")
    if x is None or y is None:
        continue
    lat, lng = sweref_to_wgs84(x, y)
    kbr_churches.append({
        "kbr_id": b["id"], "facilityPartId": b.get("facilityPartId"),
        "namn": b["namn"], "stift": b.get("stift", ""),
        "funktion": b.get("nuvarandeFunktion", ""),
        "skydd": b.get("skyddEnligtKML", False),
        "kbr_lat": lat, "kbr_lng": lng,
    })

print(f"  KBR: {len(kbr_churches)} kyrkor, {len(kbr_begravningsplatser)} begravningsplatser",
      flush=True)
print(f"  Platser: {len(platser_list)} kyrkor, {len(platser_extra_list)} övriga", flush=True)
print(f"  OSM: {len(osm_list)} platser", flush=True)

q = run_all_checks(kbr_churches_raw)

# -------------------------------------------------------------------------
# Hämta BV (Byggnadsverk) CSV
# -------------------------------------------------------------------------

bv_by_typ: dict[str, list[dict]] = defaultdict(list)
bv_csv_path = Path(__file__).parent / "data" / "bv_grundinstallning.csv"

if bv_csv_path.exists():
    print(f"Läser {bv_csv_path.name}...", flush=True)
    try:
        with open(bv_csv_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                typ = row.get("Typ av objekt")
                if typ not in ("Församlingshem", "Administrationsbyggnad", "Krematorium", "Klockstapel"):
                    continue
                try:
                    lat_str = row.get("Latitud", "").replace(",", ".")
                    lng_str = row.get("Longitud", "").replace(",", ".")
                    if not lat_str or not lng_str:
                        continue
                    lat = float(lat_str)
                    lng = float(lng_str)
                except ValueError:
                    continue
                bv_by_typ[typ].append({
                    "namn": row.get("Byggnadsverksnamn"),
                    "stift": row.get("Stiftnamn"),
                    "bv_lat": lat,
                    "bv_lng": lng,
                    "typ": typ
                })
        for t, l in bv_by_typ.items():
            print(f"  BV {t}: {len(l)}")
    except Exception as e:
        print(f"  Varning: Kunde inte läsa BV CSV: {e}")
else:
    print(f"  Varning: {bv_csv_path} saknas, hoppar över BV-data.")

# -------------------------------------------------------------------------
# Matcha: namn + geografiskt närmaste
# -------------------------------------------------------------------------

platser_by_name: dict[str, list] = defaultdict(list)
for p in platser_list:
    platser_by_name[normalize(p["namn"])].append(p)

osm_by_name: dict[str, list] = defaultdict(list)
for o in osm_list:
    osm_by_name[normalize(o["namn"])].append(o)

matched:       list[dict] = []
unmatched_kbr: list[dict] = []

for c in kbr_churches:
    key = normalize(c["namn"])
    pm, pd = closest_match(c["kbr_lat"], c["kbr_lng"],
                           platser_by_name.get(key, []), "platser_lat", "platser_lng")
    om, od = closest_match(c["kbr_lat"], c["kbr_lng"],
                           osm_by_name.get(key, []), "osm_lat", "osm_lng")
    if pm is None and om is None:
        unmatched_kbr.append(c)
        continue
    row = dict(c)
    row["typ"] = "Kyrka/kapell"
    if pm:
        row.update({"platser_id": pm["platser_id"], "platser_lat": pm["platser_lat"],
                    "platser_lng": pm["platser_lng"], "platser_slug": pm.get("platser_slug",""), "avstand_platser_m": pd})
    if om:
        row.update({"osm_id": om["osm_id"], "osm_lat": om["osm_lat"],
                    "osm_lng": om["osm_lng"], "avstand_osm_m": od})
    row["avstand_m"] = max(pd or 0, od or 0)
    matched.append(row)

# Matcha KBR-begravningsplatser mot Platser+OSM
platser_cemetery_by_name: dict[str, list] = defaultdict(list)
for p in platser_extra_list:
    if p.get("platser_typ") == "cemetery":
        platser_cemetery_by_name[normalize(p["namn"])].append(p)

osm_cemetery_by_name: dict[str, list] = defaultdict(list)
for o in osm_list:
    if o.get("osm_typ") == "begravningsplats":
        osm_cemetery_by_name[normalize(o["namn"])].append(o)

for c in kbr_begravningsplatser:
    key = normalize(c["namn"])
    pm, pd = closest_match(c["kbr_lat"], c["kbr_lng"],
                           platser_cemetery_by_name.get(key, []), "platser_lat", "platser_lng")
    om, od = closest_match(c["kbr_lat"], c["kbr_lng"],
                           osm_cemetery_by_name.get(key, []), "osm_lat", "osm_lng")
    if pm is None and om is None:
        continue
    row = dict(c)
    row["typ"] = "Begravningsplats"
    if pm:
        row.update({"platser_id": pm["platser_id"], "platser_lat": pm["platser_lat"],
                    "platser_lng": pm["platser_lng"], "platser_slug": pm.get("platser_slug",""), "avstand_platser_m": pd})
    if om:
        row.update({"osm_id": om["osm_id"], "osm_lat": om["osm_lat"],
                    "osm_lng": om["osm_lng"], "avstand_osm_m": od})
    row["avstand_m"] = max(pd or 0, od or 0)
    matched.append(row)

# Matcha övriga BV-typer
# Församlingshem -> Platser (parishhome)
parishhome_by_name: dict[str, list] = defaultdict(list)
for p in platser_extra_list:
    if p.get("platser_typ") == "parishhome":
        parishhome_by_name[normalize(p["namn"])].append(p)

for bv in bv_by_typ["Församlingshem"]:
    key = normalize(bv["namn"])
    pm, pd = closest_match(bv["bv_lat"], bv["bv_lng"],
                           parishhome_by_name.get(key, []), "platser_lat", "platser_lng",
                           max_dist=2000)
    if pm is None:
        continue
    row = {"namn": bv["namn"], "stift": bv["stift"], "kbr_lat": bv["bv_lat"], "kbr_lng": bv["bv_lng"],
           "kbr_id": None, "typ": "Församlingshem"}
    row.update({"platser_id": pm["platser_id"], "platser_lat": pm["platser_lat"],
                "platser_lng": pm["platser_lng"], "platser_slug": pm.get("platser_slug",""), "avstand_platser_m": pd, "avstand_m": pd})
    matched.append(row)

# Administrationsbyggnad -> Platser (secretariat)
secretariat_by_name: dict[str, list] = defaultdict(list)
for p in platser_extra_list:
    if p.get("platser_typ") == "secretariat":
        secretariat_by_name[normalize(p["namn"])].append(p)

for bv in bv_by_typ["Administrationsbyggnad"]:
    key = normalize(bv["namn"])
    pm, pd = closest_match(bv["bv_lat"], bv["bv_lng"],
                           secretariat_by_name.get(key, []), "platser_lat", "platser_lng",
                           max_dist=2000)
    if pm is None:
        continue
    row = {"namn": bv["namn"], "stift": bv["stift"], "kbr_lat": bv["bv_lat"], "kbr_lng": bv["bv_lng"],
           "kbr_id": None, "typ": "Administrationsbyggnad"}
    row.update({"platser_id": pm["platser_id"], "platser_lat": pm["platser_lat"],
                "platser_lng": pm["platser_lng"], "platser_slug": pm.get("platser_slug",""), "avstand_platser_m": pd, "avstand_m": pd})
    matched.append(row)

# Krematorium -> OSM (krematorium)
osm_crematorium_by_name: dict[str, list] = defaultdict(list)
for o in osm_list:
    if o.get("osm_typ") == "krematorium":
        osm_crematorium_by_name[normalize(o["namn"])].append(o)

for bv in bv_by_typ["Krematorium"]:
    key = normalize(bv["namn"])
    om, od = closest_match(bv["bv_lat"], bv["bv_lng"],
                           osm_crematorium_by_name.get(key, []), "osm_lat", "osm_lng")
    if om is None:
        continue
    row = {"namn": bv["namn"], "stift": bv["stift"], "kbr_lat": bv["bv_lat"], "kbr_lng": bv["bv_lng"],
           "kbr_id": None, "typ": "Krematorium"}
    row.update({"osm_id": om["osm_id"], "osm_lat": om["osm_lat"],
                "osm_lng": om["osm_lng"], "avstand_osm_m": od, "avstand_m": od})
    matched.append(row)

# Klockstapel -> OSM (klockstapel)
osm_campanile_by_name: dict[str, list] = defaultdict(list)
for o in osm_list:
    if o.get("osm_typ") == "klockstapel":
        osm_campanile_by_name[normalize(o["namn"])].append(o)

for bv in bv_by_typ["Klockstapel"]:
    key = normalize(bv["namn"])
    om, od = closest_match(bv["bv_lat"], bv["bv_lng"],
                           osm_campanile_by_name.get(key, []), "osm_lat", "osm_lng")
    if om is None:
        continue
    row = {"namn": bv["namn"], "stift": bv["stift"], "kbr_lat": bv["bv_lat"], "kbr_lng": bv["bv_lng"],
           "kbr_id": None, "typ": "Klockstapel"}
    row.update({"osm_id": om["osm_id"], "osm_lat": om["osm_lat"],
                "osm_lng": om["osm_lng"], "avstand_osm_m": od, "avstand_m": od})
    matched.append(row)

matched.sort(key=lambda r: r["avstand_m"], reverse=True)

# -------------------------------------------------------------------------
# Statistik
# -------------------------------------------------------------------------

avvikelser = [r for r in matched if r["avstand_m"] >= MIN_AVSTAND_M]
stats = {
    "generated":          datetime.now().isoformat(timespec="seconds"),
    "kbr_totalt":         len(kbr_churches),
    "platser_totalt":     len(platser_list),
    "osm_totalt":         len(osm_list),
    "matchade":           len(matched),
    "begravningsplatser_matchade": sum(1 for r in matched if r.get("typ") == "Begravningsplats"),
    "forsamlingshem_matchade": sum(1 for r in matched if r.get("typ") == "Församlingshem"),
    "administrationsbyggnad_matchade": sum(1 for r in matched if r.get("typ") == "Administrationsbyggnad"),
    "krematorium_matchade": sum(1 for r in matched if r.get("typ") == "Krematorium"),
    "klockstapel_matchade": sum(1 for r in matched if r.get("typ") == "Klockstapel"),
    "omatchade_kbr":      len(unmatched_kbr),
    "avvikelse_200m":     sum(1 for r in matched if r["avstand_m"] >= 200),
    "avvikelse_500m":     sum(1 for r in matched if r["avstand_m"] >= 500),
    "avvikelse_1km":      sum(1 for r in matched if r["avstand_m"] >= 1000),
    "avvikelse_5km":      sum(1 for r in matched if r["avstand_m"] >= 5000),
    "datum_omojligt":     len(q["datum_omojligt"]),
    "datum_samma_ar":     len(q["datum_samma_ar"]),
    "datum_saknas":       len(q["datum_saknas"]),
    "byggnadstid_lang":   len(q["byggnadstid_lang"]),
    "koord_utanfor":      len(q["koord_utanfor"]),
    "koord_rundad":       len(q["koord_rundad"]),
    "koord_duplikat":     len(q["koord_duplikat"]),
    "namn_duplikat":      len(q["namn_duplikat"]),
    "status_ej_aktiv":    len(q["status_ej_aktiv"]),
    "funktion_andrad":    len(q["funktion_andrad"]),
    "raa_saknas":         len(q["raa_saknas"]),
    "byggarea_saknas":    len(q["byggarea_saknas"]),
    "fastighet_saknas":   len(q["fastighet_saknas"]),
    "planform_saknas":    len(q["planform_saknas"]),
    "material_saknas":    len(q["material_saknas"]),
    "tillg_ej_prog":      len(q["tillg_ej_prog"]),
    "ej_tillganglig":     len(q["ej_tillganglig"]),
    "andrad_gammal":      len(q["andrad_gammal"]),
    "agare_mismatch":     len(q["agare_mismatch"]),
    "kbr_begravningsplatser": len(kbr_begravningsplatser),
    "osm_begravningsplatser": sum(1 for o in osm_list if o.get("osm_typ") == "begravningsplats"),
    "osm_krematorium":        sum(1 for o in osm_list if o.get("osm_typ") == "krematorium"),
    "platser_parishhome":     sum(1 for p in platser_extra_list if p["platser_typ"] == "parishhome"),
    "platser_cemetery":       sum(1 for p in platser_extra_list if p["platser_typ"] == "cemetery"),
    "platser_secretariat":    sum(1 for p in platser_extra_list if p["platser_typ"] == "secretariat"),
}

for k, v in stats.items():
    if k not in ("generated",):
        print(f"  {k}: {v}")

# -------------------------------------------------------------------------
# Skriv output
# -------------------------------------------------------------------------

(OUT_DIR / "report.json").write_text(
    json.dumps(matched, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(f"\nSkrev report.json ({(OUT_DIR/'report.json').stat().st_size//1024} KB)")

(OUT_DIR / "kbr_all.json").write_text(
    json.dumps(
        [{"kbr_id": c["kbr_id"], "namn": c["namn"], "stift": c["stift"],
          "kbr_lat": c["kbr_lat"], "kbr_lng": c["kbr_lng"]}
         for c in kbr_churches],
        ensure_ascii=False, separators=(",", ":")),
    encoding="utf-8")
print(f"Skrev kbr_all.json ({len(kbr_churches)} kyrkor)")

(OUT_DIR / "kbr_begravningsplatser.json").write_text(
    json.dumps(kbr_begravningsplatser, ensure_ascii=False, separators=(",", ":")),
    encoding="utf-8")
print(f"Skrev kbr_begravningsplatser.json ({len(kbr_begravningsplatser)} poster)")

(OUT_DIR / "platser_extra.json").write_text(
    json.dumps(platser_extra_list, ensure_ascii=False, separators=(",", ":")),
    encoding="utf-8")
print(f"Skrev platser_extra.json ({len(platser_extra_list)} poster)")

quality = {"generated": stats["generated"], **q}
(OUT_DIR / "quality.json").write_text(
    json.dumps(quality, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(f"Skrev quality.json ({(OUT_DIR/'quality.json').stat().st_size//1024} KB)")

(OUT_DIR / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
print("Skrev stats.json")

csv_fields = ["avstand_m", "avstand_platser_m", "avstand_osm_m", "namn", "stift",
              "funktion", "skydd", "kbr_id", "facilityPartId",
              "kbr_lat", "kbr_lng", "platser_id", "platser_lat", "platser_lng",
              "osm_id", "osm_lat", "osm_lng"]
with (OUT_DIR / "report.csv").open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
    w.writeheader()
    w.writerows(avvikelser)
print(f"Skrev report.csv ({len(avvikelser)} rader med avvikelse >={MIN_AVSTAND_M} m)")

# -------------------------------------------------------------------------
# Daglig snapshot
# -------------------------------------------------------------------------

snap_dir = OUT_DIR / "snapshots" / datetime.now().strftime("%Y-%m-%d")
snap_dir.mkdir(parents=True, exist_ok=True)
for _fname, _obj in [("report", matched), ("quality", quality)]:
    snap_path = snap_dir / f"{_fname}.json.gz"
    if not snap_path.exists():
        with gzip.open(snap_path, "wt", encoding="utf-8") as f:
            json.dump(_obj, f, ensure_ascii=False, separators=(",", ":"))
        print(f"Snapshot: {snap_path.relative_to(Path(__file__).parent)}")
    else:
        print(f"Snapshot redan finns: {snap_path.relative_to(Path(__file__).parent)}")
