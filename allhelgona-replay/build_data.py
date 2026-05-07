#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx>=0.27"]
# ///
"""Hämtar alla tända ljus från Bönewebbens öppna API per år och skriver
till data/candles-{year}.json + data/index.json. Klienten lazy-loadar
det år som är valt.

Datat är historiskt fryst och checkas in i repo:t. Skriptet skippar
år som redan finns - kör med `--force` för att hämta om alla år.
Detta skyddar mot att SVK rensar gamla taggar inför 2026.

Inga secrets - API:et är öppet.

Format index.json:
{
  "fetched": "...",
  "years": [
    { "year": 2020, "tag": "allhelgona2020", "count": 4900, "file": "candles-2020.json" },
    ...
  ]
}

Format candles-{year}.json:
{
  "year": 2025, "tag": "allhelgona2025",
  "window_from": "...", "window_to": "...",
  "fetched": "...", "count": 16559,
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
DATA = ROOT / "data"
INDEX_OUT = DATA / "index.json"

BASE = "https://be.svenskakyrkan.se/api"
BATCH = 1000
MAX_PAGES = 50

# Tagsystemet börjar 2020 - äldre taggar finns inte i API:et.
YEARS = [2020, 2021, 2022, 2023, 2024, 2025]

TZ = ZoneInfo("Europe/Stockholm")


def parse_iso_z(s: str) -> int:
    """ISO 8601 UTC -> epoch seconds (int)."""
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


def window_for(year: int) -> tuple[int, int]:
    """Replay-fönstret per år: 1 okt 00:00 - 11 nov 00:00 (Europe/Stockholm).
    Övre gränsen exklusiv: "till och med 10 nov 23:59"."""
    return (
        int(datetime(year, 10, 1, 0, 0, tzinfo=TZ).timestamp()),
        int(datetime(year, 11, 11, 0, 0, tzinfo=TZ).timestamp()),
    )


def fetch_year(client: httpx.Client, tag: str) -> list[tuple[int, float, float]]:
    out: list[tuple[int, float, float]] = []
    seen: set[int] = set()
    for page in range(MAX_PAGES):
        offset = page * BATCH
        url = f"{BASE}/geo-positions/tags/{tag}/candles/{BATCH}/{offset}/"
        r = client.get(url)
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
            if tid in seen:
                continue
            seen.add(tid)
            try:
                out.append((parse_iso_z(created), float(lat), float(lng)))
            except (ValueError, TypeError):
                continue
        print(f"    sida {page + 1}: {len(thoughts)} st (totalt {len(out)})",
              file=sys.stderr, flush=True)
        if len(thoughts) < BATCH:
            break
        time.sleep(0.1)
    return out


def write_year(year: int, client: httpx.Client) -> dict | None:
    tag = f"allhelgona{year}"
    out_path = DATA / f"candles-{year}.json"

    print(f"\nÅr {year} (tag={tag}) ...", file=sys.stderr)
    raw = fetch_year(client, tag)
    if not raw:
        print(f"  inga ljus, skippar", file=sys.stderr)
        return None
    raw.sort(key=lambda c: c[0])

    win_from, win_to = window_for(year)
    candles = [c for c in raw if win_from <= c[0] < win_to]
    skipped = len(raw) - len(candles)
    if skipped:
        print(f"  filtrerade bort {skipped} ljus utanför 1 okt - 10 nov {year}",
              file=sys.stderr)

    rounded = [[ts, round(lat, 5), round(lng, 5)] for ts, lat, lng in candles]
    payload = {
        "year": year,
        "tag": tag,
        "window_from": datetime.fromtimestamp(win_from, tz=timezone.utc)
                              .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_to":   datetime.fromtimestamp(win_to, tz=timezone.utc)
                              .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fetched": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count": len(rounded),
        "candles": rounded,
    }

    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    kb = out_path.stat().st_size // 1024
    print(f"  skrev {out_path.name} ({kb} KB, {len(rounded)} ljus)",
          file=sys.stderr)
    return {
        "year": year,
        "tag": tag,
        "count": len(rounded),
        "file": out_path.name,
    }


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    force = "--force" in sys.argv

    entries: list[dict] = []
    with httpx.Client(timeout=60) as client:
        for year in YEARS:
            out_path = DATA / f"candles-{year}.json"
            if out_path.exists() and not force:
                # Återanvänd befintlig - läs metadata för index
                existing = json.loads(out_path.read_text(encoding="utf-8"))
                entries.append({
                    "year": existing["year"],
                    "tag": existing["tag"],
                    "count": existing["count"],
                    "file": out_path.name,
                })
                print(f"År {year}: {out_path.name} finns redan, använder befintlig "
                      f"({existing['count']} ljus)",
                      file=sys.stderr)
                continue
            entry = write_year(year, client)
            if entry:
                entries.append(entry)

    if not entries:
        print("\nIngen data skriven.", file=sys.stderr)
        return

    index = {
        "fetched": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "years": entries,
    }
    INDEX_OUT.write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    total = sum(e["count"] for e in entries)
    print(f"\nSkrev {INDEX_OUT.name} ({len(entries)} år, {total} ljus totalt)",
          file=sys.stderr)


if __name__ == "__main__":
    main()
