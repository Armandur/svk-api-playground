# signage-platser

Signage-vy för en specifik plats - visar dagens öppettider och
veckoschema. Tänkt att fällas in i en zon på en signage-skärm utanför
en kyrka eller ett församlingshem.

Referens-platser: **Härnösands domkyrka** (id
`5dab016f-18f3-4973-92d8-69779653a1ef`).

## Stack

- Vanilla HTML/CSS/JS, ingen bundler, inga byggsteg.
- `refresh.py` (uv-inline-deps, Python 3.12) hämtar plats från
  Platser-API:t och skriver till `place.json`.
- Klienten laddar `place.json` via `fetch()` och beräknar
  öppet/stängt-status helt klient-sidigt.
- API-nyckeln finns **bara** på maskinen som kör `refresh.py` - den
  exponeras aldrig till signage-skärmen.

## Filer

- `index.html` - hela vyn (HTML + CSS + JS inline).
- `refresh.py` - hämta plats, skriv `place.json`. Körs med cron eller
  systemd-timer.
- `place.json` - cachad data (gitignored).

## Konfiguration

Sätt env-vars (eller `.env` i denna mapp / repo-roten):

```bash
APIKEY_PROD=<din SVK-API-nyckel>
PLACE_ID=5dab016f-18f3-4973-92d8-69779653a1ef
```

`refresh.py` läser dessa och skriver `place.json` i samma mapp.

## Kör lokalt

```bash
# 1. Hämta data
APIKEY_PROD=... PLACE_ID=... uv run refresh.py

# 2. Servera index.html på en lokal webbserver (annars blockerar
#    browsers fetch() av filsystem-paths)
python3 -m http.server 8000
# -> http://localhost:8000/

# 3. Stega om data
uv run refresh.py    # uppdaterar place.json
# Sidan auto-laddar om data var 60:e sekund (se REFRESH_DATA_MS i index.html)
```

## Driftsättning (skiss)

För riktigt signage-läge:

- Lägg `refresh.py` på cron `*/10 * * * *` (var 10:e min).
- Servera mappen via valfri statisk webbserver (Caddy, nginx,
  python -m http.server).
- Öppna sidan i kiosk-läge (Chromium `--kiosk --noerrdialogs ...`).
- Skärmen behöver bara nätverks-access till webbservern, inte till
  Platser-API:t.

## Datakontrakt mot Platser

Vi läser `openHours` från `/place/{id}` (se
[`docs/modules/PLATSER.md`](../docs/modules/PLATSER.md)). Strukturen är:

- `openHours.periods[]` - lista av perioder.
- Varje period har valfria `validFrom` / `validTo` (ISO-datum) och
  `days.{mo,tu,we,th,fr,sa,su}[]` med `{from, to}`-intervall.
- Tom dag-array = stängt.
- Flera intervall per dag stöds (lunchstängt).
- Tider är i platsens lokala tidszon (Europa/Stockholm för svenska
  platser - vi antar det implicit, ingen `timeZoneId`-konvertering
  görs).

## Öppna frågor / TODO

- Hantera **avvikelser** (storhelger, tillfälliga stängningar).
  Inget formellt schema-stöd; ev. `openHours.info` som fritextfält.
  Testa mot några platser med kända storhelgsstängningar.
- `validFrom`/`validTo` med tom sträng - dokumenterat som "ingen gräns",
  hantera även `null` och saknad nyckel.
- Hantera överlappande perioder. Idag väljer vi första matchande -
  räcker för "sommarsäsong + standard"-fall.
- Felhantering om `place.json` inte kan laddas (visa cachat eller
  generisk "öppettider ej tillgängliga"-text).
- Layout för olika skärmstorlekar (signage-skärmar är ofta porträtt
  eller udda aspect ratios).