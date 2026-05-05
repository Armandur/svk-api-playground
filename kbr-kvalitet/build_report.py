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

Kör:
  APIKEY_PROD=<nyckel> uv run kbr-kvalitet/build_report.py
"""

from __future__ import annotations

import csv
import json
import math
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
from matching import MAX_MATCH_M, closest_match, haversine, normalize, sweref_to_wgs84  # noqa: E402

load_dotenv(Path(__file__).parent.parent / ".env")

API_KEY = os.environ.get("APIKEY_PROD") or os.environ.get("APIKEY")
if not API_KEY:
    sys.exit("Sätt APIKEY_PROD eller APIKEY i miljön.")

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

OUT_DIR          = Path(__file__).parent / "data"
MIN_AVSTAND_M    = 200
LANG_BYGG        = 300    # år
STALE_DATE       = datetime(2020, 1, 1)
STATUS_EJ_AKTIV  = {"Kyrkan används inte"}

# -------------------------------------------------------------------------
# Hämta KBR
# -------------------------------------------------------------------------

print("Hämtar KBR...", flush=True)
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

kbr_churches: list[dict] = []

# Befintliga kvalitetslistor
q_datum_omojligt:   list[dict] = []
q_datum_samma_ar:   list[dict] = []
q_datum_saknas:     list[dict] = []
q_byggnadstid_lang: list[dict] = []
q_koord_utanfor:    list[dict] = []
q_koord_rundad:     list[dict] = []

# Nya kvalitetslistor
q_status_ej_aktiv:     list[dict] = []
q_funktion_andrad:     list[dict] = []
q_raa_saknas:          list[dict] = []
q_byggarea_saknas:     list[dict] = []
q_fastighet_saknas:    list[dict] = []
q_planform_saknas:     list[dict] = []
q_material_saknas:     list[dict] = []
q_tillg_ej_prog:       list[dict] = []
q_ej_tillganglig:      list[dict] = []
q_andrad_gammal:       list[dict] = []
q_agare_mismatch:      list[dict] = []

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
            x, y = b.get("xKoordinat"), b.get("yKoordinat")
            if x is None or y is None:
                continue
            lat, lng = sweref_to_wgs84(x, y)
            bygg, invigd = b.get("nybyggnadFran"), b.get("invigning")
            namn, stift  = b["namn"], b.get("stift", "")
            base = {"kbr_id": b["id"], "namn": namn, "stift": stift,
                    "funktion": b.get("nuvarandeFunktion", ""),
                    "kbr_lat": lat, "kbr_lng": lng}

            # --- Datumkvalitet ---
            if bygg and invigd:
                if bygg > invigd:
                    q_datum_omojligt.append({**base, "nybyggnadFran": bygg,
                                             "invigning": invigd, "diff_år": invigd - bygg})
                elif bygg == invigd:
                    q_datum_samma_ar.append({**base, "år": bygg})
                elif invigd - bygg > LANG_BYGG:
                    q_byggnadstid_lang.append({**base, "nybyggnadFran": bygg,
                                               "invigning": invigd, "byggnadstid": invigd - bygg})
            elif bygg is None and invigd is None:
                q_datum_saknas.append({**base, "saknas": "båda"})
            elif bygg is None:
                q_datum_saknas.append({**base, "saknas": "nybyggnadFran", "invigning": invigd})
            else:
                q_datum_saknas.append({**base, "saknas": "invigning", "nybyggnadFran": bygg})

            # --- Koordinatkvalitet ---
            if not (55.0 < lat < 70.5 and 10.0 < lng < 25.0):
                q_koord_utanfor.append({**base, "kbr_lat": lat, "kbr_lng": lng})
            if int(x) % 1000 == 0 and int(y) % 1000 == 0:
                q_koord_rundad.append({**base, "kbr_x": int(x), "kbr_y": int(y)})

            # --- Status ---
            freq = b.get("anvandningsfrekvens", "")
            if freq in STATUS_EJ_AKTIV:
                q_status_ej_aktiv.append({**base, "anvandningsfrekvens": freq,
                                          "invigning": invigd})

            nuv = b.get("nuvarandeAnvandning", "")
            ursp = b.get("ursprungligAnvandning", "")
            if nuv and ursp:
                nuv_kyrka  = nuv.lower().startswith("kyrka")
                ursp_kyrka = ursp.lower().startswith("kyrka")
                if nuv_kyrka != ursp_kyrka:
                    q_funktion_andrad.append({**base, "ursprunglig": ursp,
                                              "nuvarande": nuv, "invigning": invigd})

            # --- Komplettering ---
            if not b.get("identitetRAA"):
                q_raa_saknas.append({**base, "invigning": invigd,
                                     "skyddEnligtKML": b.get("skyddEnligtKML", "")})
            if not b.get("byggarea"):
                q_byggarea_saknas.append({**base, "invigning": invigd})
            if not b.get("fastighetsbeteckning"):
                q_fastighet_saknas.append({**base, "invigning": invigd})
            if not b.get("planform"):
                q_planform_saknas.append({**base, "invigning": invigd})
            stomme = b.get("materialStomme") or ""
            fasad  = b.get("materialFasad") or ""
            if not stomme or not fasad:
                saknar = "båda" if (not stomme and not fasad) \
                         else ("stomme" if not stomme else "fasad")
                q_material_saknas.append({**base, "saknar": saknar,
                                          "materialStomme": stomme or "-",
                                          "materialFasad": fasad or "-"})

            # --- Tillgänglighet ---
            prog  = b.get("handlingsprogramTillganglighet") or ""
            anp   = b.get("tillganglighetsanpassning") or ""
            if not prog or prog == "Handlingsprogram finns inte":
                q_tillg_ej_prog.append({**base, "program": prog or "(tomt)", "anpassning": anp})
            if anp == "Inte tillgänglighetsanpassad":
                q_ej_tillganglig.append({**base, "anpassning": anp, "program": prog})

            # --- Förvaltning ---
            agare = b.get("agandeEnhet") or ""
            geo   = b.get("geografiskEnhet") or ""
            if agare and geo and agare != geo:
                q_agare_mismatch.append({**base, "agandeEnhet": agare,
                                         "geografiskEnhet": geo})

            andrad_str = b.get("andradDatum") or ""
            if andrad_str:
                try:
                    andrad = datetime.fromisoformat(andrad_str)
                    if andrad.replace(tzinfo=None) < STALE_DATE:
                        q_andrad_gammal.append({**base,
                            "andradDatum": andrad_str[:10],
                            "skapadDatum": (b.get("skapadDatum") or "")[:10],
                            "invigning": invigd})
                except ValueError:
                    pass

            kbr_churches.append({
                "kbr_id": b["id"], "facilityPartId": b.get("facilityPartId"),
                "namn": namn, "stift": stift, "funktion": b.get("nuvarandeFunktion", ""),
                "skydd": b.get("skyddEnligtKML", False),
                "kbr_lat": lat, "kbr_lng": lng,
            })

        print(f"  KBR: {len(kbr_churches)} hämtade", end="\r", flush=True)
        if len(batch) < 100:
            break
        offset += 100

print(f"\n  KBR klar: {len(kbr_churches)} kyrkor", flush=True)

# -------------------------------------------------------------------------
# Hämta KBR Begravningsplatser
# -------------------------------------------------------------------------

print("Hämtar KBR Begravningsplatser...", flush=True)
kbr_begravningsplatser: list[dict] = []
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
            kbr_begravningsplatser.append({
                "kbr_id": b["id"], "namn": b["namn"],
                "stift": b.get("stift", ""),
                "kbr_lat": lat, "kbr_lng": lng,
            })
        print(f"  KBR Begravningsplatser: {len(kbr_begravningsplatser)} hämtade",
              end="\r", flush=True)
        if len(batch) < 100:
            break
        offset += 100
print(f"\n  KBR Begravningsplatser klar: {len(kbr_begravningsplatser)}", flush=True)

# Duplikatkoordinater + namn
coord_groups: dict[tuple, list] = defaultdict(list)
for c in kbr_churches:
    coord_groups[(c["kbr_lat"], c["kbr_lng"])].append(
        {"kbr_id": c["kbr_id"], "namn": c["namn"], "stift": c["stift"]})
q_koord_duplikat = [
    {"kbr_lat": k[0], "kbr_lng": k[1], "kyrkor": v}
    for k, v in coord_groups.items() if len(v) > 1
]

name_stift: dict[str, list] = defaultdict(list)
for c in kbr_churches:
    name_stift[f"{c['namn']}||{c['stift']}"].append(
        {"kbr_id": c["kbr_id"], "stift": c["stift"],
         "kbr_lat": c["kbr_lat"], "kbr_lng": c["kbr_lng"]})
q_namn_duplikat = [
    {"namn": k.split("||")[0], "stift": k.split("||")[1], "kyrkor": v}
    for k, v in name_stift.items() if len(v) > 1
]

# -------------------------------------------------------------------------
# Hämta SVK Platser
# -------------------------------------------------------------------------

print("Hämtar SVK Platser...", flush=True)
platser_list: list[dict] = []
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
        platser_list.append({"platser_id": p.get("id"), "namn": p.get("name", ""),
                              "platser_slug": p.get("slug", ""),
                              "platser_lat": round(coords[1], 6),
                              "platser_lng": round(coords[0], 6)})
    offset += len(results)
    print(f"  Platser: {len(platser_list)}/{total_hits}", end="\r", flush=True)
    if offset >= total_hits:
        break
    time.sleep(0.05)

print(f"\n  Platser klar: {len(platser_list)} kyrkor", flush=True)

# -------------------------------------------------------------------------
# Hämta SVK Platser - övriga typer (parishhome, cemetery, secretariat)
# -------------------------------------------------------------------------

print("Hämtar SVK Platser (övriga typer)...", flush=True)
platser_extra_list: list[dict] = []
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
            platser_extra_list.append({
                "platser_id": p.get("id"), "namn": p.get("name", ""),
                "platser_slug": p.get("slug", ""),
                "platser_lat": round(coords[1], 6), "platser_lng": round(coords[0], 6),
                "platser_typ": _platstyp,
            })
        _offset_p += len(_results)
        print(f"  Platser {_platstyp}: {sum(1 for x in platser_extra_list if x['platser_typ']==_platstyp)}/{_total_p}",
              end="\r", flush=True)
        if _offset_p >= _total_p:
            break
        time.sleep(0.05)
print(f"\n  Platser övriga klar: {len(platser_extra_list)} totalt", flush=True)

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
# Hämta OSM via Overpass
# -------------------------------------------------------------------------

print("Hämtar OSM via Overpass...", flush=True)
osm_list: list[dict] = []
body = urllib.parse.urlencode({"data": OVERPASS_QUERY}).encode("utf-8")
hdrs = {"Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "svk-api-playground/0.1 (rasmus.pettersson.vik@gmail.com)"}
osm_ok = False

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
                is_cemetery = (tags.get("landuse") == "cemetery"
                               or tags.get("amenity") == "grave_yard")
                is_crematorium = tags.get("amenity") == "crematorium"
                is_campanile = tags.get("man_made") == "campanile"
                if is_cemetery:
                    osm_typ = "begravningsplats"
                elif is_crematorium:
                    osm_typ = "krematorium"
                elif is_campanile:
                    osm_typ = "klockstapel"
                else:
                    osm_typ = "kyrka"
                osm_list.append({"osm_id": el["id"], "namn": name,
                                  "osm_lat": round(ola, 6), "osm_lng": round(olo, 6),
                                  "osm_typ": osm_typ})
            osm_ok = True
            break
        except Exception as e:
            print(f"  Overpass {url} fel: {e}", flush=True)
            time.sleep(15 if attempt == 0 else 0)
    if osm_ok:
        break

print(f"  OSM {'klar: ' + str(len(osm_list)) + ' platser' if osm_ok else 'misslyckades'}", flush=True)

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

# ÄNDRING B – Matcha KBR-begravningsplatser mot Platser+OSM
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

# ÄNDRING C – Matcha övriga BV-typer
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
    "datum_omojligt":     len(q_datum_omojligt),
    "datum_samma_ar":     len(q_datum_samma_ar),
    "datum_saknas":       len(q_datum_saknas),
    "byggnadstid_lang":   len(q_byggnadstid_lang),
    "koord_utanfor":      len(q_koord_utanfor),
    "koord_rundad":       len(q_koord_rundad),
    "koord_duplikat":     len(q_koord_duplikat),
    "namn_duplikat":      len(q_namn_duplikat),
    "status_ej_aktiv":    len(q_status_ej_aktiv),
    "funktion_andrad":    len(q_funktion_andrad),
    "raa_saknas":         len(q_raa_saknas),
    "byggarea_saknas":    len(q_byggarea_saknas),
    "fastighet_saknas":   len(q_fastighet_saknas),
    "planform_saknas":    len(q_planform_saknas),
    "material_saknas":    len(q_material_saknas),
    "tillg_ej_prog":      len(q_tillg_ej_prog),
    "ej_tillganglig":     len(q_ej_tillganglig),
    "andrad_gammal":      len(q_andrad_gammal),
    "agare_mismatch":     len(q_agare_mismatch),
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

OUT_DIR.mkdir(exist_ok=True)

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

quality = {
    "generated":          stats["generated"],
    "datum_omojligt":     q_datum_omojligt,
    "datum_samma_ar":     q_datum_samma_ar,
    "datum_saknas":       q_datum_saknas,
    "byggnadstid_lang":   q_byggnadstid_lang,
    "koord_utanfor":      q_koord_utanfor,
    "koord_rundad":       q_koord_rundad,
    "koord_duplikat":     q_koord_duplikat,
    "namn_duplikat":      q_namn_duplikat,
    "status_ej_aktiv":    q_status_ej_aktiv,
    "funktion_andrad":    q_funktion_andrad,
    "raa_saknas":         q_raa_saknas,
    "byggarea_saknas":    q_byggarea_saknas,
    "fastighet_saknas":   q_fastighet_saknas,
    "planform_saknas":    q_planform_saknas,
    "material_saknas":    q_material_saknas,
    "tillg_ej_prog":      q_tillg_ej_prog,
    "ej_tillganglig":     q_ej_tillganglig,
    "andrad_gammal":      q_andrad_gammal,
    "agare_mismatch":     q_agare_mismatch,
}
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
