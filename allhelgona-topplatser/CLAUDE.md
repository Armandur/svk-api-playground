# allhelgona-topplatser - Claude-anteckningar

Pilot under [`svk-api-playground`](../CLAUDE.md). Visar de svenska
platser där flest digitala ljus tänts på Bönewebben under allhelgona
2020-2025. Täcker kyrkor, kapell, kyrkogårdar och församlingshem.

## Stack

- Vanilla JS + HTML + CSS, ingen bundler eller karta
- Mörkt tema som matchar `kbr-tidslinje` (varm beige + guld på mörkbrun)
- 3 000+ rader renderas i en enkel `<table>` - browsern hanterar det

## Datapipeline

`build_data.py`:

1. Hämtar `geo-positions/tags/allhelgona{year}/.../rooms` per år (öppet
   API, ingen nyckel). Returen har 700-2 900 platser per år. Ger:
   `{count, name, slug, position_lat, position_long}`.
2. Slår ihop per slug till `{slug, name, lat, lng, ljus: {år: count}}`.
3. **`normalize_coords()`** korrigerar trasig position via
   `COORD_OVERRIDES` eller heuristisk lat/lng-swap (om lat utanför
   svenska range men lng inom).
4. Per plats görs point-in-polygon mot tre kartlager:
   - `ls-visualize/data/stift.geojson` - stift (samma fil för alla år;
     stift ändras i praktiken aldrig)
   - `forsamlingsindelning-historik/data/pastorat_{year}.geojson` -
     pastorat per år (sammanslagningar händer)
   - `forsamlingsindelning-historik/data/forsamlingar_{year}.geojson` -
     församling per år
5. **`FORSAML_OVERRIDES`** override:ar pastorat/församling för
   icke-territoriella församlingar (Hovförsamlingen, Karlskrona
   amiralitet, Tyska S:ta Gertrud osv). Point-in-polygon ger den
   territoriella - vi behöver det organisatoriska.
6. **Stift-buffer** på 5 km - om punkt-in-polygon misslyckas, fall
   tillbaka på närmaste polygonvertex inom marginalen. Fångar gränseffekter
   (Karesuando ligger 1 km från finska gränsen och faller annars utanför
   Luleå stifts polygon).

Resultat skrivs till `data/leaderboard.json` (~1.3 MB).

Datat är historiskt fryst och checkas in - skriptet skippar om filen
finns. `--force` hämtar om.

## Match-rate

| Lager   | Match    |
|---------|----------|
| Stift   | 99,4 % (3 423 / 3 444) |
| Pastorat per år | 99-100 % |
| Församling per år | 99-100 % |

De ~21 platser utan stift är utlandsförsamlingar (Svenska kyrkan i
London, New York, Helsingfors etc) och två platser där koordinater
saknas helt och inte kan disambigueras (`slottskyrkogaaaarden`,
`ansgarskyrkan`). Se `FELANMALAN.md`.

## Designval

- **Inget kartlager.** Det här är en lista, inte en visualisering.
  Tabellen är vad användaren faktiskt vill bläddra i.
- **Sparkline per rad.** Sex stapler 2020-2025 visar trend per plats.
  Topp-året markeras (accent), valt år lyser i flame-färg. Skala är
  *lokal* (relativ till varje plats egen max) - så små platser inte
  ser tomma ut bredvid storstadsplatser.
- **Total-kolumnen är dynamisk.** När år-väljaren står på "Total"
  visas summan 2020-2025; när ett enstaka år är valt visas det årets
  värde och tabellen sorteras om.
- **Sub-info per år.** "Stift / församling / pastorat" baseras på
  valt år (eller senaste år platsen hade ljus om "Total" är valt) -
  speglar rätt indelning historiskt vid sammanslagningar.
- **Pastorat döljs när det är samma som församlingen** (självständig
  församling - vanligt fall).

## Vanliga ändringar

- **Lägg till år**: `YEARS`-listan i `build_data.py` + säkerställ att
  pastorat/forsamlingar-filer finns för året i
  `forsamlingsindelning-historik`.
- **Ny icke-territoriell församling**: lägg till slug i
  `FORSAML_OVERRIDES` med `{forsamling, pastorat}`.
- **Ny korrigerad koordinat**: lägg till slug i `COORD_OVERRIDES` med
  `(lat, lng)` och uppdatera `FELANMALAN.md`.
- **Strängare stift-fallback**: ändra `STIFT_BUFFER_KM`. Lägre värde
  = striktare matchning men fler unmatched i gränsfall.
