# KBR-kvalitet

Datakvalitetsrapport för Kyrkobyggnadsregistret (KBR). Hämtar ~3 500
kyrkor från KBR-API:t och jämför mot SVK Platser-API:t och OSM via
Overpass. Rapporterar koordinatavvikelser och ett brett urval
datakvalitetsproblem.

## Kör lokalt

```bash
# Bygg datamängden (kräver APIKEY_PROD i env, ~3 min inkl. OSM-hämtning)
APIKEY_PROD=<nyckel> uv run kbr-kvalitet/build_report.py

# Starta servern (från repo-roten)
./start.sh
# Öppna: http://ubuntu-ai:8088/kbr-kvalitet/
```

## Rapporten

Sex flikar i webbgränssnittet:

| Flik | Innehåll |
|---|---|
| Koordinatavvikelser | KBR vs Platser-API och OSM, karta med tre markörer per kyrka |
| Datumkvalitet | Omöjlig datumodning, lång byggnadstid, saknade datum |
| Koordinatkvalitet | Utanför Sverige, rundade koordinater, duplikat |
| Namnkvalitet | Duplikatnamn inom stift |
| Status & avyttring | Kyrkan används inte, fundamentala funktionsändringar |
| Komplettering & förvaltning | Saknade fält (RAA, byggarea, fastighetsbeteckning, planform, material), tillgänglighet, stale-poster, ägar/geo-mismatch |

Alla kvalitetstabeller har en ⌖-knapp per rad som hoppar till
KBR-koordinaten på kartan. Skriv ut / PDF-knapp döljer kartan och
formaterar alla fynd som en sammanhållen rapport.

## Output-filer

| Fil | Innehåll |
|---|---|
| `data/report.json` | Koordinatjämförelse KBR vs Platser/OSM (för kartan) |
| `data/quality.json` | Alla kvalitetsproblem kategoriserade |
| `data/stats.json` | Sammanfattande statistik |
| `data/report.csv` | Koordinatavvikelser >= 200 m (för rapportering till kyrkokansliet) |

Alla datafiler är gitignorerade och byggs lokalt.

## Matchningsalgoritm

Koordinatjämförelsen matchar på normaliserat kyrkonamn och väljer bland
namnkandidater den geografiskt närmaste (cap 200 km). Det eliminerar
korslandsmatcher för kyrkor med identiska namn i olika delar av landet.

## Tekniskt

- Leaflet + vanilla JS, ingen bundler
- KBR-API: SWEREF99TM via pyproj, 3 485 kyrkor
- Platser-API: 4 488 platser av typ churchAndChapel
- OSM: Overpass API, ~4 700 kristna gudstjänstplatser i Sverige
- PEP 723 inline-deps (httpx, pyproj) - ingen separat installation
