#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx>=0.27"]
# ///
"""Hämtar hela kyrkoåret från SVK:s publika churchcalendar-endpoint
och skriver till data/kyrkoaret.json. Kör dagligen i CI så att
Pages-versionen alltid har aktuella entries (kyrkoåret skiftar
1 advent varje år).

Använder publik klientside-nyckel - inga secrets behövs.
"""
from __future__ import annotations

import json
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data" / "kyrkoaret.json"

# Publik klientside-nyckel som SVK:s egen webbplats använder.
API_KEY = "139ff33b-4451-4f0f-b397-1f4ec9307a87"
URL = "https://www.svenskakyrkan.se/webapi/api-v2/churchcalendar"


def main() -> None:
    r = httpx.get(URL, params={"apikey": API_KEY}, timeout=30)
    r.raise_for_status()
    entries = r.json()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(entries, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    first = entries[0].get("startDate", "?")[:10]
    last = entries[-1].get("startDate", "?")[:10]
    print(f"Skrev {OUT.relative_to(ROOT.parent)} "
          f"({OUT.stat().st_size // 1024} KB, {len(entries)} entries, "
          f"{first} - {last})")


if __name__ == "__main__":
    main()
