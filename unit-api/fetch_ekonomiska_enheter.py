# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx>=0.27"]
# ///
"""Hämtar alla aktuella ekonomiska enheter från UnitAPI och skriver
namnen till data/ekonomiska_enheter.csv (en per rad).

Ekonomiska enheter = enheter med egen ekonomi i SVK:s organisation:
  - Stift (13 st)
  - Sammfällighet / pastorat (229 st, observera SVK:s stavning med 2 m)
  - FörsamlingE / församling med egen ekonomi (354 st)

Församlingar utan egen ekonomi (som tillhör pastorat) ingår inte.

Aktuella = validUntil saknas eller ligger i framtiden.

Kräver APIKEY_PROD i ../.env.
"""
from __future__ import annotations

import csv
import os
from datetime import date
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT.parent / ".env"
OUT_PATH = ROOT / "data" / "ekonomiska_enheter.csv"

BASE = "https://api.svenskakyrkan.se/externwebb/api-v2/odata"
PAGE_SIZE = 1000  # OData-server tillåter max 1000

EKONOMISKA_TYPER = {"Stift", "Sammfällighet", "FörsamlingE"}

# unitId=1 är "Kyrkokansliet - Ägarweb" i UnitAPI (unitType=Ingen).
# Det är CMS-rotnoden men motsvarar organisatoriskt Trossamfundet Svenska
# kyrkan på riksnivå. Vi byter namn vid export till det som faktiskt avses.
TROSSAMFUNDET_UNIT_ID = 1
TROSSAMFUNDET_NAMN = "Trossamfundet Svenska kyrkan"

# Icke-territoriella församlingar (ITF) går inte att identifiera från
# API-fält - parentUnitId är null på alla FörsamlingE och inga andra
# fält skiljer dem. Hårdkodad lista enligt Svenska kyrkans officiella
# förteckning.
ITF_UNIT_IDS = {
    97,    # Hovförsamlingen (Stockholm)
    98,    # Tyska S:ta Gertruds församling (Stockholm)
    99,    # Finska församlingen (Stockholm)
    774,   # Karlskrona Amiralitetsförsamling
    2436,  # Tyska Christinae församling (Göteborg)
}


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def fetch_all_units(api_key: str) -> list[dict]:
    select = "unitId,name,unitType,validUntil,activeFrom,parentUnitId,stiftCode"
    headers = {"SvkAuthSvc-ApiKey": api_key}
    units: list[dict] = []
    skip = 0
    with httpx.Client(timeout=30) as client:
        while True:
            url = f"{BASE}/units"
            params = {"$top": PAGE_SIZE, "$skip": skip, "$select": select}
            r = client.get(url, params=params, headers=headers)
            r.raise_for_status()
            page = r.json()["value"]
            units.extend(page)
            print(f"  hämtade {len(page)} (skip={skip})")
            if len(page) < PAGE_SIZE:
                break
            skip += PAGE_SIZE
    return units


def is_aktuell(unit: dict, today: str) -> bool:
    vu = unit.get("validUntil")
    return vu is None or vu > today


def main() -> None:
    env = {**os.environ, **load_env(ENV_PATH)}
    api_key = env.get("APIKEY_PROD") or env.get("APIKEY_TEST")
    if not api_key:
        raise SystemExit("Saknar APIKEY_PROD eller APIKEY_TEST i miljö/.env")

    print("Hämtar alla enheter från UnitAPI ...")
    units = fetch_all_units(api_key)
    print(f"Totalt: {len(units)} enheter")

    today = date.today().isoformat()

    stift_by_code = {
        u["stiftCode"]: u["name"]
        for u in units
        if u["unitType"] == "Stift" and u.get("stiftCode")
    }

    ekonomiska = [
        u for u in units
        if u["unitType"] in EKONOMISKA_TYPER and is_aktuell(u, today)
    ]

    # Lägg till Trossamfundet Svenska kyrkan (unitId=1) - se kommentar ovan
    trossamfundet = next(
        (u for u in units if u["unitId"] == TROSSAMFUNDET_UNIT_ID),
        None,
    )
    if trossamfundet:
        synthetic = dict(trossamfundet)
        synthetic["name"] = TROSSAMFUNDET_NAMN
        synthetic["unitType"] = "Trossamfund"
        ekonomiska.append(synthetic)

    ekonomiska.sort(key=lambda u: u["name"].lower())

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        for u in ekonomiska:
            if u["unitId"] == TROSSAMFUNDET_UNIT_ID:
                stift = "Nationell nivå"
            elif u["unitType"] == "Stift":
                stift = u["name"]
            else:
                stift = stift_by_code.get(u.get("stiftCode") or "", "")
            w.writerow([u["name"], stift])

    by_type: dict[str, int] = {}
    for u in ekonomiska:
        by_type[u["unitType"]] = by_type.get(u["unitType"], 0) + 1
    itf_count = sum(1 for u in ekonomiska if u["unitId"] in ITF_UNIT_IDS)
    print(f"\nSkrev {len(ekonomiska)} aktuella ekonomiska enheter -> {OUT_PATH.relative_to(ROOT.parent)}")
    for t, n in sorted(by_type.items()):
        print(f"  {t}: {n}")
    print(f"  varav icke-territoriella församlingar (ITF): {itf_count}")


if __name__ == "__main__":
    main()
