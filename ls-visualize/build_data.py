#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Bygg ls-visualize/data/loneservice.json från lokal CSV.

Källa: data/loneservice.csv (UTF-8 BOM, semikolon, CRLF).
Kolumner: Stift;Enhet;Löneservice;Antal konton

CSV:n är inkopierad från /mnt/vmworkspace/Löneservice.csv. Modulen
är fristående - alla beroenden ligger under data/.

Outputstruktur:
{
  "enheter": { "<enhetsnamn>": { "stift": "...", "ja": true/false, "konton": 39 }, ... },
  "stiftsenheter": { "<stift>": { "ja": true/false, "konton": N } },  # där Enhet==Stift
  "ovrigt": [ { "namn": "...", "stift": "...", "ja": ..., "konton": N } ],  # ej i geojson
  "trossamfund": { "namn": "...", "ja": ..., "konton": 954 },
  "stift_summary": { "<stift>": { "ja_enheter": N, "totalt_enheter": N,
                                  "ja_konton": N, "totalt_konton": N } }
}
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
CSV_PATH = DATA / "loneservice.csv"
GEOJSON_PATH = DATA / "ekonomiska_enheter.geojson"
OUT_PATH = DATA / "loneservice.json"

TROSSAMFUNDET = "Trossamfundet Svenska kyrkan"


def main() -> int:
    if not CSV_PATH.exists():
        print(f"Saknar {CSV_PATH}")
        return 1
    if not GEOJSON_PATH.exists():
        print(f"Saknar {GEOJSON_PATH}")
        return 1

    with GEOJSON_PATH.open(encoding="utf-8") as fh:
        gj = json.load(fh)
    geojson_namn = {f["properties"]["namn"].strip() for f in gj["features"]}

    with CSV_PATH.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter=";"))

    enheter: dict[str, dict] = {}
    stiftsenheter: dict[str, dict] = {}
    ovrigt: list[dict] = []
    trossamfund: dict | None = None
    summary: dict[str, dict] = {}

    for r in rows:
        stift = r["Stift"].strip()
        enhet = r["Enhet"].strip()
        ja = r["Löneservice"].strip().lower() == "ja"
        konton_raw = r["Antal konton"].strip().replace(" ", "")
        konton = int(konton_raw) if konton_raw else 0

        s = summary.setdefault(stift, {
            "ja_enheter": 0, "totalt_enheter": 0,
            "ja_konton": 0, "totalt_konton": 0,
        })
        s["totalt_enheter"] += 1
        s["totalt_konton"] += konton
        if ja:
            s["ja_enheter"] += 1
            s["ja_konton"] += konton

        if stift == TROSSAMFUNDET:
            trossamfund = {"namn": enhet, "ja": ja, "konton": konton}
            continue

        if enhet == stift:
            stiftsenheter[stift] = {"ja": ja, "konton": konton}
            continue

        if enhet in geojson_namn:
            enheter[enhet] = {"stift": stift, "ja": ja, "konton": konton}
        else:
            ovrigt.append({"namn": enhet, "stift": stift, "ja": ja, "konton": konton})

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "enheter": enheter,
        "stiftsenheter": stiftsenheter,
        "ovrigt": ovrigt,
        "trossamfund": trossamfund,
        "stift_summary": summary,
        "_meta": {
            "kalla": "Löneservice.csv (vmworkspace)",
            "antal_enheter_matchade": len(enheter),
            "antal_geojson": len(geojson_namn),
            "antal_ovrigt": len(ovrigt),
        },
    }
    with OUT_PATH.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    print(f">> skrev {OUT_PATH} ({OUT_PATH.stat().st_size} bytes)")
    print(f"   enheter matchade: {len(enheter)}/{len(geojson_namn)} geojson-features")
    print(f"   stiftsenheter: {len(stiftsenheter)}")
    print(f"   ovriga (ej i geojson): {len(ovrigt)}")
    print(f"   trossamfund: {trossamfund}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
