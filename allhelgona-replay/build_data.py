#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx>=0.27"]
# ///
"""Hämtar alla tända ljus från senaste allhelgonahelgen via Bönewebbens
publika API och skriver till data/candles.json i kompakt format.

Datat är historiskt fryst (allhelgona 2025 är förbi) och checkas in i
repo:t. Skriptet skippar om filen redan finns - kör med `--force` för
att hämta om från API:et. Detta skyddar mot att SVK rensar datat inför
allhelgona 2026.

Inga secrets - API:et är öppet.

Format:
{
  "tag": "allhelgona2025",
  "fetched": "2026-05-07T...",
  "count": 16586,
  "first_lit": "2025-10-27T18:11:53Z",
  "last_lit":  "2026-03-31T12:45:43Z",
  "candles": [[ts_epoch_seconds, lat, lng], ...]   # sorterad ts ASC
}
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data" / "candles.json"

TAG = "allhelgona2025"
BASE = "https://be.svenskakyrkan.se/api"
BATCH = 1000
MAX_PAGES = 50  # 50_000 ljus räcker; bryter när tomt svar kommer ändå

# Replay-fönster - vi vill bara visa själva allhelgonaperioden, inte
# enstaka ljus som tänts långt efter helgen. Tider i Europe/Stockholm
# (lokal tid). Övre gränsen är exklusiv: 11 nov 00:00 = "till och med
# 10 nov 23:59".
TZ = ZoneInfo("Europe/Stockholm")
WINDOW_FROM_TS = int(datetime(2025, 10, 1, 0, 0, tzinfo=TZ).timestamp())
WINDOW_TO_TS   = int(datetime(2025, 11, 11, 0, 0, tzinfo=TZ).timestamp())


def parse_iso_z(s: str) -> int:
    """ISO 8601 UTC -> epoch seconds (int)."""
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


def fetch_all() -> list[tuple[int, float, float]]:
    out: list[tuple[int, float, float]] = []
    seen_ids: set[int] = set()
    with httpx.Client(timeout=60) as c:
        for page in range(MAX_PAGES):
            offset = page * BATCH
            url = f"{BASE}/geo-positions/tags/{TAG}/candles/{BATCH}/{offset}/"
            r = c.get(url)
            r.raise_for_status()
            data = r.json()["data"]
            thoughts = data.get("thoughts", [])
            if not thoughts:
                break
            for t in thoughts:
                tid = t.get("id")
                lat = t.get("position_lat")
                lng = t.get("position_long")
                created = t.get("created")
                if tid is None or lat is None or lng is None or not created:
                    continue
                if tid in seen_ids:
                    continue
                seen_ids.add(tid)
                try:
                    out.append((parse_iso_z(created), float(lat), float(lng)))
                except (ValueError, TypeError):
                    continue
            print(f"  sida {page + 1}: {len(thoughts)} st (totalt {len(out)})",
                  file=sys.stderr, flush=True)
            if len(thoughts) < BATCH:
                break
            time.sleep(0.1)
    return out


def main() -> None:
    force = "--force" in sys.argv
    if OUT.exists() and not force:
        size_kb = OUT.stat().st_size // 1024
        print(f"{OUT.relative_to(ROOT.parent)} finns redan ({size_kb} KB). "
              f"Kör med --force för att hämta om.", file=sys.stderr)
        return

    print(f"Hämtar tag={TAG} ...", file=sys.stderr)
    candles = fetch_all()
    candles.sort(key=lambda c: c[0])

    raw_count = len(candles)
    candles = [c for c in candles if WINDOW_FROM_TS <= c[0] < WINDOW_TO_TS]
    skipped = raw_count - len(candles)
    if skipped:
        print(f"  filtrerade bort {skipped} ljus utanför 1 okt - 10 nov 2025",
              file=sys.stderr)

    # Avrunda koordinater till 5 decimaler (~1 m precision räcker gott).
    rounded = [[ts, round(lat, 5), round(lng, 5)] for ts, lat, lng in candles]

    payload = {
        "tag": TAG,
        "window_from": datetime.fromtimestamp(WINDOW_FROM_TS, tz=timezone.utc)
                              .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_to":   datetime.fromtimestamp(WINDOW_TO_TS, tz=timezone.utc)
                              .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fetched": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count": len(rounded),
        "first_lit": (datetime.fromtimestamp(rounded[0][0], tz=timezone.utc)
                      .strftime("%Y-%m-%dT%H:%M:%SZ")) if rounded else None,
        "last_lit":  (datetime.fromtimestamp(rounded[-1][0], tz=timezone.utc)
                      .strftime("%Y-%m-%dT%H:%M:%SZ")) if rounded else None,
        "candles": rounded,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    kb = OUT.stat().st_size // 1024
    print(f"Skrev {OUT.relative_to(ROOT.parent)} "
          f"({kb} KB, {len(rounded)} ljus, "
          f"{payload['first_lit']} - {payload['last_lit']})",
          file=sys.stderr)


if __name__ == "__main__":
    main()
