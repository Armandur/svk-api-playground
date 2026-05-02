# forsamlingskarta-enklaver

Hittar och guidar genom alla **enklaver** och **exklaver** bland Svenska
kyrkans församlingar - alltså polygondelar som ligger åtskilda från
huvudområdet eller helt inneslutna i en grannförsamling.

- **Exklav:** en del av en församling som ligger geografiskt åtskild
  (MultiPolygon med flera del-polygoner; alla utom den största räknas
  som exklaver).
- **Enklav:** en församlings polygon som ligger helt innesluten i en
  *annan* församlings polygon (sällsynt men förekommer historiskt).

## Snabbstart

```bash
# 1) Bygg datafilen (~12 MB shapefile-zip hämtas, ~220 KB resultat)
uv run forsamlingskarta-enklaver/build_enclaves.py

# 2) Servera lokalt
./start.sh
# -> http://ubuntu-ai:8088/forsamlingskarta-enklaver/
```

## Funktioner

- **Karta** med alla enklaver/exklaver färglagda - vinröd för enklaver,
  guld för exklaver.
- **Rundtur** top-left: knappar `‹ Föreg` / `Nästa ›` panorerar och
  zoomar till nästa avvikelse i listan.
- **Tangentbord**: pilar vänster/höger för rundtur.
- **Visa alla / Dölj alla** för att fokusera på ett område i taget.
- **Klick på polygon** hoppar direkt till den i rundturen.
- **Popup** visar församlingsnamn, typ, omslutande församling (för
  enklaver) eller del-index (för exklaver) och approximativ areal.

Listan sorteras: enklaver först (sällsyntare), sedan exklaver i
fallande areal-ordning - största kuriosa-fallen kommer först.

## Datafilen

`build_enclaves.py` hämtar `forsamlingar_2026-01-01.zip` direkt från
`api.svenskakyrkan.se/kartor/`, simplifierar geometrin (Douglas-Peucker
10 m, topologi-bevarande), reprojicerar SWEREF 99 TM → WGS84 och kör
detektering i minnet. Skriver bara `data/enklaver.geojson` (~220 KB)
- ingen koppling till `forsamlingskarta-leaflet`.

Detektering:
- **Exklaver:** för varje MultiPolygon-feature: alla del-polygoner
  utöver den största räknas som exklaver.
- **Enklaver:** STRtree-index över alla del-polygoner;
  `cand_part.contains(part)` med kandidat från annan församling.

`data/`-mappen är gitignored - bygg lokalt.

## Senaste körning

| Typ | Antal |
|---|---|
| Exklaver | 270 |
| Enklaver | 0 |

Ingen enklav efter 10 m simplifiering - topologin förlorar exakt
inneslutning. För att hitta historiska enklaver kan tolerance sänkas
till 0 i `build_enclaves.py`, på bekostnad av större filstorlek.
