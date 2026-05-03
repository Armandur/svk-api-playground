#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["shapely>=2.0", "pyproj>=3.6"]
# ///
"""Matchar SVK-kyrkor mot OSM-kyrkor via närmsta-granne med radie-tröskel
och skriver data/diff.geojson med tre kategorier:
  - matched: kyrkor som finns i båda källor (parar bästa kandidat per SVK)
  - svk_only: SVK-kyrkor utan OSM-match inom radien
  - osm_only: OSM-kyrkor som inte parades med någon SVK-kyrka

Default-radie 100 m. Avstånd beräknas i SWEREF 99 TM (meter, EPSG:3006)
för korrekt fysisk distans på Sveriges latituder.

Kör: uv run osm-konsistenscheck/build_diff.py [radius_m]
"""

from __future__ import annotations

import json
import math
import re
import sys
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import Point
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DEFAULT_RADIUS_M = 100
# Namn-likhet under denna tröskel räknas som "mismatch" (matchade
# kyrkor där SVK och OSM tror det är olika namn).
NAME_MISMATCH_THRESHOLD = 0.55
# Denominations vi accepterar som "Svenska kyrkan" på OSM-sidan.
SVK_DENOMINATIONS = {"lutheran", "church_of_sweden", "protestant"}


def haversine(lon1, lat1, lon2, lat2):
    R = 6371000  # radius of Earth in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2)**2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    return 2 * R * math.asin(math.sqrt(a))


def osm_missing_tags(osm_tags: dict | None) -> list[str]:
    """Returnera lista av OSM-taggar som SAKNAS för en SvK-matchande
    kyrka. Komplett tagging på OSM borde ha amenity=place_of_worship,
    religion=christian och en av SVK_DENOMINATIONS som denomination."""
    t = osm_tags or {}
    missing = []
    if t.get("amenity") != "place_of_worship":
        missing.append("amenity")
    if t.get("religion") != "christian":
        missing.append("religion")
    if t.get("denomination") not in SVK_DENOMINATIONS:
        missing.append("denomination")
    return missing


def normalize_name(s: str | None) -> str:
    if not s: return ""
    s = s.lower()
    # Ersätt vanliga substitutioner som annars sänker similarity
    s = s.replace("s:t", "sankt").replace("s:ta", "sankta")
    s = re.sub(r"\b(kyrka|kapell|church|chapel)\b", "", s)
    s = re.sub(r"[^\wåäö ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def name_similarity(a: str | None, b: str | None) -> float | None:
    na, nb = normalize_name(a), normalize_name(b)
    if not na or not nb: return None
    return round(SequenceMatcher(None, na, nb).ratio(), 3)


def project_features(features: list[dict], transformer: Transformer):
    """Returnera (lista av (Point i SWEREF, original_props, original_lonlat))."""
    rows = []
    for f in features:
        lon, lat = f["geometry"]["coordinates"]
        x, y = transformer.transform(lon, lat)
        rows.append((Point(x, y), f["properties"], [lon, lat]))
    return rows


def _name_priority(name: str | None) -> int:
    """Lägre = bättre primär-kyrka. Används vid koordinat-dedup för
    att välja vilken av flera SVK-poster på samma plats som ska behållas."""
    n = (name or "").lower().strip()
    if n.endswith(" kyrka") or n.endswith("kyrkan"): return 0
    if n.endswith(" kapell") or n.endswith("kapellet"): return 1
    if "kyrka" in n or "kapell" in n: return 2
    return 5


def dedup_svk_by_coord(features: list[dict]) -> tuple[list[dict], int]:
    """SVK Platser har ibland flera poster på samma koordinat (t.ex.
    'Mo kyrka' + 'Trons kapell Mo' + 'Annan plats Mo' alla på exakt
    samma punkt). De är inte separata byggnader i OSM. Behåll bara
    primär-kyrkan (lägst _name_priority) per unik koordinat."""
    by_coord: dict[tuple, dict] = {}
    for f in features:
        lon, lat = f["geometry"]["coordinates"]
        # 5 decimaler ≈ 1 m precision - räcker för "samma plats"
        key = (round(lon, 5), round(lat, 5))
        existing = by_coord.get(key)
        if existing is None:
            by_coord[key] = f
        else:
            cur_p = _name_priority(f["properties"].get("name"))
            ex_p = _name_priority(existing["properties"].get("name"))
            if cur_p < ex_p:
                by_coord[key] = f
    kept = list(by_coord.values())
    return kept, len(features) - len(kept)


def main(argv: list[str]) -> int:
    radius = float(argv[1]) if len(argv) > 1 else DEFAULT_RADIUS_M
    svk_path = DATA / "svk_kyrkor.geojson"
    osm_path = DATA / "osm_kyrkor.geojson"
    if not (svk_path.exists() and osm_path.exists()):
        print("FEL: kör build_svk.py och build_osm.py först", file=sys.stderr)
        return 2

    svk = json.loads(svk_path.read_text(encoding="utf-8"))["features"]
    osm = json.loads(osm_path.read_text(encoding="utf-8"))["features"]
    svk, dedup_count = dedup_svk_by_coord(svk)
    print(f"SVK: {len(svk)} kyrkor (dedup: -{dedup_count} på samma koord), "
          f"OSM: {len(osm)} kyrkor", flush=True)

    tr = Transformer.from_crs("EPSG:4326", "EPSG:3006", always_xy=True)
    svk_rows = project_features(svk, tr)
    osm_rows = project_features(osm, tr)

    # Greedy global matching: bygg alla SVK-OSM-par inom radien,
    # sortera på avstånd, plocka kortaste först. Hindrar en
    # närliggande "Annan plats X" eller "Trons kapell X" från att
    # snappa OSM-pinnen som egentligen tillhör huvudkyrkan.
    osm_points = [r[0] for r in osm_rows]
    tree = STRtree(osm_points)
    # (distance, -similarity, i, j) - tie-break på namnlikhet så att
    # två SVK-poster på samma koord (t.ex. "X församling" och "X kyrka")
    # inte kapar OSM-pinnen från den med bättre namn-match.
    pairs: list[tuple[float, float, int, int]] = []
    for i, (svk_pt, svk_props, _) in enumerate(svk_rows):
        for j in tree.query(svk_pt.buffer(radius)):
            d = svk_pt.distance(osm_points[j])
            if d <= radius:
                sim = name_similarity(
                    svk_props.get("name"),
                    osm_rows[j][1].get("name")) or 0.0
                pairs.append((d, -sim, i, j))
    pairs.sort()
    svk_match: dict[int, tuple[int, float]] = {}
    svk_consumed: set[int] = set()
    osm_consumed: set[int] = set()
    for d, _neg_sim, i, j in pairs:
        if i in svk_consumed or j in osm_consumed:
            continue
        svk_consumed.add(i)
        osm_consumed.add(j)
        svk_match[i] = (j, d)

    matched = []
    svk_only = []
    for i, (svk_pt, svk_props, svk_lonlat) in enumerate(svk_rows):
        if i not in svk_match:
            svk_only.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": svk_lonlat},
                "properties": {**svk_props, "kategori": "svk_only"},
            })
            continue
        j, d = svk_match[i]
        _, osm_props, osm_lonlat = osm_rows[j]
        sim = name_similarity(svk_props.get("name"), osm_props.get("name"))
        missing = osm_missing_tags(osm_props.get("tags"))
        matched.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": svk_lonlat},
            "properties": {
                "kategori": "matched",
                "svk_namn": svk_props.get("name"),
                "svk_id": svk_props.get("id"),
                "svk_slug": svk_props.get("slug"),
                "svk_url": svk_props.get("url"),
                "svk_owner_name": svk_props.get("owner_name"),
                "osm_id": osm_props.get("osm_id"),
                "osm_namn": osm_props.get("name"),
                "osm_denomination": osm_props.get("denomination"),
                "osm_lonlat": osm_lonlat,
                "distance_m": round(d, 1),
                "name_similarity": sim,
                "name_mismatch": sim is not None and sim < NAME_MISMATCH_THRESHOLD,
                "osm_missing_tags": missing,
            },
        })

    # Wikidata-berikning: vilka osm_only har wikidata-tagg som pekar mot
    # en SvK-stiftstillhörig kyrka? De flyttas konceptuellt från "annan
    # denomination" till "förmodlig SVK Platser-miss".
    wd_set: dict[str, str] = {}
    wd_set_path = DATA / "wikidata_svk_set.json"
    if wd_set_path.exists():
        wd_set = json.loads(wd_set_path.read_text())["items"]

    osm_only = []
    for j, (_, osm_props, osm_lonlat) in enumerate(osm_rows):
        if j in osm_consumed:
            continue
        props = {**osm_props, "kategori": "osm_only"}
        wd = osm_props.get("wikidata")
        if wd and wd in wd_set:
            props["likely_svk_miss"] = True
            props["wikidata_diocese"] = wd_set[wd]
        osm_only.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": osm_lonlat},
            "properties": props,
        })

    # KBR-berikning
    kbr_path = DATA / "kbr.geojson"
    kbr_only = []
    kbr_summary = {"total": 0, "matched": 0, "only": 0, "osm_errors_200m": 0}

    if kbr_path.exists():
        kbr_data = json.loads(kbr_path.read_text(encoding="utf-8"))["features"]
        kbr_summary["total"] = len(kbr_data)

        # Pool av ankarpunkter: matched (OSM-coord), svk_only (SVK-coord), osm_only (OSM-coord)
        anchor_pool = []
        for f in matched:
            anchor_pool.append({
                "lat": f["properties"]["osm_lonlat"][1],
                "lng": f["properties"]["osm_lonlat"][0],
                "feature": f,
                "type": "matched",
                "svk_lonlat": f["geometry"]["coordinates"]
            })
        for f in svk_only:
            anchor_pool.append({
                "lat": f["geometry"]["coordinates"][1],
                "lng": f["geometry"]["coordinates"][0],
                "feature": f,
                "type": "svk_only"
            })
        for f in osm_only:
            anchor_pool.append({
                "lat": f["geometry"]["coordinates"][1],
                "lng": f["geometry"]["coordinates"][0],
                "feature": f,
                "type": "osm_only"
            })

        for f in kbr_data:
            kbr_name = f["properties"].get("namn")
            kbr_lng, kbr_lat = f["geometry"]["coordinates"]
            norm_kbr = normalize_name(kbr_name)

            candidates = []
            for anchor in anchor_pool:
                feat = anchor["feature"]
                # Match på exakt namn eller normaliserat namn
                match_found = False
                names_to_check = []
                if anchor["type"] == "matched":
                    names_to_check = [feat["properties"].get("svk_namn"), feat["properties"].get("osm_namn")]
                elif anchor["type"] == "svk_only":
                    names_to_check = [feat["properties"].get("name")]
                elif anchor["type"] == "osm_only":
                    names_to_check = [feat["properties"].get("name")]

                for n in names_to_check:
                    if not n: continue
                    if n.lower() == kbr_name.lower() or normalize_name(n) == norm_kbr:
                        match_found = True
                        break

                if match_found:
                    dist = haversine(kbr_lng, kbr_lat, anchor["lng"], anchor["lat"])
                    if dist <= 200000: # 200 km
                        candidates.append((dist, anchor))

            if candidates:
                # Sortera på avstånd, prioritera matched/osm_only framför svk_only vid lika avstånd
                def sort_key(c):
                    dist, anchor = c
                    prio = 0 if anchor["type"] in ("matched", "osm_only") else 1
                    return (dist, prio)

                candidates.sort(key=sort_key)
                best_dist, best_anchor = candidates[0]
                feat_props = best_anchor["feature"]["properties"]
                feat_props["kbr_id"] = f["properties"].get("kbr_id")
                feat_props["kbr_lat"] = kbr_lat
                feat_props["kbr_lng"] = kbr_lng
                feat_props["kbr_osm_distance_m"] = int(best_dist)
                if best_anchor["type"] == "matched":
                    feat_props["kbr_platser_distance_m"] = int(haversine(kbr_lng, kbr_lat, best_anchor["svk_lonlat"][0], best_anchor["svk_lonlat"][1]))
                elif best_anchor["type"] == "svk_only":
                    feat_props["kbr_platser_distance_m"] = int(best_dist)

                kbr_summary["matched"] += 1
                if feat_props["kbr_osm_distance_m"] > 200:
                    kbr_summary["osm_errors_200m"] += 1
            else:
                kbr_only.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [kbr_lng, kbr_lat]},
                    "properties": {
                        "kategori": "kbr_only",
                        "kbr_id": f["properties"].get("kbr_id"),
                        "kbr_namn": kbr_name,
                        "stift": f["properties"].get("stift"),
                        "skydd": f["properties"].get("skydd")
                    }
                })
                kbr_summary["only"] += 1

    out = {
        "type": "FeatureCollection",
        "features": matched + svk_only + osm_only + kbr_only,
    }
    out_path = DATA / "diff.geojson"
    out_path.write_text(
        json.dumps(out, separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8")
    namnmismatch = sum(1 for m in matched if m["properties"].get("name_mismatch"))
    long_distance = sum(1 for m in matched if m["properties"].get("distance_m", 0) > 50)
    osm_kvalitet = sum(1 for m in matched if m["properties"].get("osm_missing_tags"))
    osm_missing_breakdown = {"amenity": 0, "religion": 0, "denomination": 0}
    for m in matched:
        for t in m["properties"].get("osm_missing_tags") or []:
            osm_missing_breakdown[t] = osm_missing_breakdown.get(t, 0) + 1
    # Topp-N denominations bland osm_only för UI-filter
    denom_counts: dict[str, int] = {}
    for f in osm_only:
        d = f["properties"].get("denomination") or "(saknas)"
        denom_counts[d] = denom_counts.get(d, 0) + 1
    osm_denominations = sorted(
        ({"value": k, "antal": v} for k, v in denom_counts.items()),
        key=lambda x: x["antal"], reverse=True)

    likely_svk_miss = sum(1 for f in osm_only
                          if f["properties"].get("likely_svk_miss"))
    summary = {
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "svk_source_at": datetime.fromtimestamp(
            svk_path.stat().st_mtime, tz=timezone.utc).isoformat(timespec="seconds"),
        "osm_source_at": datetime.fromtimestamp(
            osm_path.stat().st_mtime, tz=timezone.utc).isoformat(timespec="seconds"),
        "radius_m": radius,
        "antal_svk": len(svk),
        "antal_osm": len(osm),
        "matched": len(matched),
        "svk_only": len(svk_only),
        "osm_only": len(osm_only),
        "osm_only_likely_svk_miss": likely_svk_miss,
        "matched_namnmismatch": namnmismatch,
        "matched_distance_over_50m": long_distance,
        "matched_osm_taggbrist": osm_kvalitet,
        "matched_osm_missing_breakdown": osm_missing_breakdown,
        "osm_denominations": osm_denominations,
        "kbr_total": kbr_summary["total"],
        "kbr_matched": kbr_summary["matched"],
        "kbr_only": kbr_summary["only"],
        "kbr_osm_errors_200m": kbr_summary["osm_errors_200m"],
    }
    if kbr_path.exists():
        summary["kbr_source_at"] = datetime.fromtimestamp(
            kbr_path.stat().st_mtime, tz=timezone.utc).isoformat(timespec="seconds")

    (DATA / "diff_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nResultat (radie {radius:g} m):")
    print(f"  matched:  {len(matched):>5}  (varav {namnmismatch} namnmismatch, {long_distance} >50m)")
    print(f"  svk_only: {len(svk_only):>5}  (saknas i OSM)")
    print(f"  osm_only: {len(osm_only):>5}  (saknas i SVK eller annan denomination)")
    print(f"  kbr_only: {len(kbr_only):>5}  (finns i KBR men inte i Platser/OSM)")
    print(f"\nSkrev {out_path.name} ({out_path.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
