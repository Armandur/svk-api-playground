# Allhelgona-topplatser

Leaderboard över de platser där flest digitala ljus tänts på Svenska
kyrkans Bönewebb under allhelgona 2020-2025. Täcker kyrkor, kapell,
kyrkogårdar och församlingshem - inte bara kyrkor, därav "topplatser".

## Snabbstart

```bash
# Datat (data/leaderboard.json) är committat - inget bygge behövs.
cd ..
./start.sh
# -> http://localhost:8088/allhelgona-topplatser/

# För att hämta om från API:et:
uv run allhelgona-topplatser/build_data.py --force
```

## Data

`build_data.py` hämtar `geo-positions/tags/allhelgona{2020..2025}/.../rooms`
för varje år och slår ihop per plats. Geografi och organisatorisk
tillhörighet bestäms via point-in-polygon mot SVK:s kartor:

- `ls-visualize/data/stift.geojson` - stift (förändras inte i praktiken)
- `forsamlingsindelning-historik/data/pastorat_{år}.geojson` - pastorat
  ("ekonomisk enhet"), per år eftersom indelningen ändras
- `forsamlingsindelning-historik/data/forsamlingar_{år}.geojson` -
  församling, per år

Inga API-nycklar - allt går via öppna källor.

Output `data/leaderboard.json`:

```json
{
  "fetched": "...",
  "years": [2020, 2021, 2022, 2023, 2024, 2025],
  "platser": [
    {
      "slug": "...", "name": "...", "lat": 59.5, "lng": 15.9,
      "stift": "Stockholms stift",
      "per_ar": {
        "2020": { "e": "Pastoratet", "f": "Församlingen" },
        ...
      },
      "ljus": { "2020": 12, ..., "2025": 22 },
      "total": 100
    }
  ]
}
```

## Korrigeringar

`build_data.py` har två konstanter för att hantera kända datafel i
Bönewebbens API:

- `COORD_OVERRIDES` - korrekta koordinater för platser med felregistrerad
  position (0,0 eller swappade lat/lng).
- `FORSAML_OVERRIDES` - mappar icke-territoriella församlingar (Karlskrona
  amiralitetsförsamling, Tyska S:ta Gertruds, Hovförsamlingen etc) till
  rätt församling, eftersom point-in-polygon ger den territoriella.

Se [`FELANMALAN.md`](FELANMALAN.md) för en lista över de kända felen i
API:t som vi rapporterar in till SVK.

## Filer

- `index.html` - sticky-tabell med sökfält, stift- och årsväljare
- `style.css` - mörkt tema, samma palett som `kbr-tidslinje`
- `app.js` - klientside-filter och sortering, bygger 3 000+ rader på en
  gång (snabbt nog för moderna webbläsare)
- `build_data.py` - paginerar Bönewebben, gör point-in-polygon, applicerar
  overrides
- `data/leaderboard.json` - resultatet, committat i repo:t
- `FELANMALAN.md` - lista över felaktiga platser i Bönewebbens API

## Deploy

Bygger via `.github/workflows/pages-deploy.yml` till
`https://armandur.github.io/svk-api-playground/allhelgona-topplatser/`.
Datat är committat i repo:t (immunt mot framtida API-rens).
