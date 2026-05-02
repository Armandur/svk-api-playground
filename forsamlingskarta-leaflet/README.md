# forsamlingskarta-leaflet

Interaktiv karta över Svenska kyrkans platser med Leaflet + OpenStreetMap.
Klickbara markörer visar plats-info, ägar-församling, faciliteter och
länk till svenskakyrkan.se.

## Snabbstart

```bash
# Lokal proxy (från repo-roten med .env satt)
./start.sh
# -> http://ubuntu-ai:8088/forsamlingskarta-leaflet/
```

Eller hosta `index.html` var som helst och peka direkt mot SVK med
read-only-nyckel:

```
https://din-server/forsamlingskarta-leaflet/?apikey=<key>
```

## URL-parametrar

| Param | Beskrivning |
|---|---|
| `?apikey=<key>` | Read-only API-nyckel - hämta direkt mot SVK utan dev-server |
| `?owner_id=<id>` eller `?owner_id=<id1>,<id2>,...` | Filtrera på ägar-enhet (församling/pastorat) |
| `?nearby=<lon>,<lat>&radius=<m>` | Geosök inom radie i meter (WGS84-koordinater) |
| `?limit=<n>` | Max antal platser (default 500) |
| `?layer=<lager>` | Gränser att rita. Default `auto` växlar baserat på zoom (stift→kontrakt→ekonomiska_enheter→forsamlingar). Override med `stift`, `kontrakt`, `forsamlingar`, `ekonomiska_enheter` eller `none`. |

### Exempel

```
# Härnösands pastorats platser
?owner_id=20271

# Platser inom 5 km från en punkt
?nearby=17.94,62.63&radius=5000

# Direkt mot SVK utan dev-server
?apikey=<key>&owner_id=20271
```

## Kartlager (gränser)

`build_kartor.py` hämtar shapefile-zip:ar från
`api.svenskakyrkan.se/kartor/`, reprojicerar SWEREF 99 TM → WGS84
och skriver till `data/`.

```bash
uv run forsamlingskarta-leaflet/build_kartor.py            # alla lager
uv run forsamlingskarta-leaflet/build_kartor.py stift      # bara stift
```

Tillgängliga lager: `forsamlingar`, `kontrakt`, `stift`,
`ekonomiska_enheter`. Year hårdkodat till 2026-01-01 - ändra i
scriptet eller utöka med argument vid behov.

Storlek efter Douglas-Peucker-simplifiering i SWEREF-meter
(`shapely.simplify(tolerance, preserve_topology=True)`):

| Lager | Antal | Tolerance | Storlek |
|---|---|---|---|
| `stift.geojson` | 13 | 50 m | 208 KB |
| `kontrakt.geojson` | 96 | 25 m | 938 KB |
| `ekonomiska_enheter.geojson` | 568 | 10 m | 3.6 MB |
| `forsamlingar.geojson` | 1251 | 10 m | 5.6 MB |

10 m tolerance = exakt på street-level zoom. Topology-bevarande
ser till att grannförsamlingar inte får glapp på delade gränser.
Tolerance per lager justeras i `SIMPLIFY_TOLERANCE_M`-dicten i
`build_kartor.py`.

Lager väljs via `?layer=`. Default `auto` växlar baserat på zoom:

| Zoom | Lager |
|---|---|
| ≤ 6 (Hela Sverige) | `stift` |
| 7-8 (Region) | `kontrakt` |
| 9-10 (Stiftsområde) | `ekonomiska_enheter` |
| ≥ 11 (Kommunnivå+) | `forsamlingar` |

Lager hämtas lazy och cachas, så ett lager laddas bara en gång även
om man zoomar fram och tillbaka. Override med `?layer=<namn>` för att
låsa till en specifik vy, eller `?layer=none` för att dölja alla
gränser.

`data/`-mappen är gitignored för att inte blåsa upp repot - bygg
lokalt vid behov.

## Funktioner

- **Plats-markörer** med klustrering (`leaflet.markercluster`) - de
  9474 platserna grupperas vid utzoomning, sprider ut sig vid inzoom.
- **Plats-typ-ikoner** - färgade cirklar med initial:
  K=kyrka/kapell (vinröd), F=församlingshem (mörkgrön),
  A=kansli (gold), B=begravningsplats (mörklila),
  V=vallokal (orange), · = övrigt
- **Dynamisk inladdning** baserat på kartans vy. Vid panorering/zoom
  hämtas platser inom det nya synliga området via `?nearby=` på
  Platser-API:t. Cache av kända plats-ID:n förhindrar dubbletter.
- **Gränslager** med automatisk växling mellan stift / kontrakt /
  ekonomiska enheter / församlingar baserat på zoom-nivå (eller
  manuellt via radio-väljare top-right).
- **Teckenförklaring** bottom-right.

## TODO

- Stiftsväljare som filter (klick på stift → bara dess platser).
- Radera stale-markörer när man panorerar långt bort (idag växer
  cachet obegränsat).
- Olika ikoner per plats-typ via SVG istället för bara färg+initial.

Se [`docs/modules/PLATSER.md`](../docs/modules/PLATSER.md) för
datakontrakt, filter-syntax och `geolocation`-formatet (WGS84,
ordning lon/lat).
