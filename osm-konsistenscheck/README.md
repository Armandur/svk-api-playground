# osm-konsistenscheck

Jämför kyrkor i SVK Platser-API:t mot OpenStreetMap för att hitta:

- **Matchade**: båda källorna har en kyrka inom 100 m radie.
- **Bara SVK**: SVK-kyrkor utan motsvarighet i OSM (saknas, har fel
  koordinater eller >100 m bort).
- **Bara OSM**: OSM-kyrkor utan SVK-match (frikyrkor, ortodoxa,
  katolska, fel taggning, eller verkliga luckor i SVK Platser).

Bygger på Levenshtein-namnlikhet, OSM-taggbrist-check och iD-editor-
länkar för att göra det enkelt att bidra tillbaka till OSM.

## Live

Publicerat på <https://armandur.github.io/svk-api-playground/osm-konsistenscheck/>.
GitHub Actions bygger om dagligen 04:00 UTC + vid push på
`osm-konsistenscheck/**` och deployar till GitHub Pages
(`.github/workflows/osm-deploy.yml`). På Pages-deployen är "Hämta nytt
data"-knappen dold eftersom det inte finns någon serverside-rebuild att
trigga - cron sköter färskheten.

## Snabbstart

```bash
./start.sh                                   # http://ubuntu-ai:8088/
```

Öppna http://ubuntu-ai:8088/osm-konsistenscheck/ och klicka **Hämta nytt
data** uppe till höger - knappen kör SVK + OSM + diff i bakgrunden,
visar pulserande status per steg och reloadar sidan när det är klart.
Hela rebuilden tar 1-3 min beroende på Overpass-belastning.

Headern visar `Senast uppdaterad: YYYY-MM-DD HH:MM (rel.)` så det syns
direkt om datat är färskt eller månader gammalt.

### Manuell rebuild (utan UI)

```bash
./osm-konsistenscheck/rebuild.sh            # kräver att ./start.sh redan kör
```

Eller stegvis om något specifikt steg behöver köras om:

```bash
APIKEY=... uv run osm-konsistenscheck/build_svk.py    # SVK Platser (~1.7 MB)
uv run osm-konsistenscheck/build_osm.py               # OSM via Overpass (~2.4 MB)
uv run osm-konsistenscheck/build_diff.py              # default 100 m radie
```

`build_svk.py` går direkt mot `api.svenskakyrkan.se` och kräver `APIKEY`
(eller `APIKEY_PROD`) i miljön. Sätt `PLATSER_BASE=http://localhost:8088/api/platser`
för att gå via dev-proxyn istället - då behövs ingen nyckel i shellet.
`./start.sh` läser `.env` automatiskt så `rebuild.sh` (som går via proxyn)
slipper hantera nyckeln själv.

Overpass är notoriskt opålitlig - `build_osm.py` försöker tre Overpass-
spegelservrar (overpass-api.de, kumi.systems, private.coffee) två gånger
var med 15 s backoff innan den ger upp.

## Funktioner

- **Pie-chart-kluster**: klustermarkörer visar fördelningen mellan
  matched/svk_only/osm_only som conic-gradient med totalantal i mitten.
- **Färgkodade pins**: grön (matched), vinröd (svk_only), blå (osm_only).
  Gula ringar för namn-mismatch, blå för OSM-taggbrist (vid inzoom).
- **Sub-filter för matched**: "Visa bara namn-mismatch", "Visa bara
  >50 m", "Visa bara OSM-taggbrist". Klustret uppdateras automatiskt.
- **Avståndslinjer**: streckade linjer mellan SVK och OSM för
  matched-par >50 m bort.
- **OSM-denomination-filter**: kollapsbar lista med top-12
  denominations - filtrera bort katolska/baptist/etc från osm_only.
- **Sökruta** top-left: lazy-loaded sök med debounce, sortering på
  prefix-matchningar, färgad prick per kategori, klick zoomar.
- **Bakgrundskartor**: OpenStreetMap, Esri-satellit, hybrid (sat+labels).
- **Popup-länkar**:
  - "Redigera i iD" för OSM-noden (auto-öppnar editor på rätt feature)
  - "Lägg till i iD-editor" för svk_only (zoomar till position)
  - "SVK plats-sida" till `svenskakyrkan.se/platser/<slug>`
  - "Församlingens sida" om angiven
- **CSV-export** av "Bara SVK" - 1053 poster med name/owner/city/koord/url.
- **In-app rebuild**: knapp i headern triggar `build_svk.py` + `build_osm.py`
  + `build_diff.py` via en POST mot `/osm-konsistenscheck/api/rebuild`.
  Status pollas var 2:a sekund (`/api/rebuild/status`), pulserande
  indikator visar aktuellt steg, sidan reloadar när det är klart.
  Bara ett rebuild-jobb i taget (parallell-POST → 409).

## Resultat (radie 100 m, 2026-05-02)

| Kategori | Antal |
|---|---|
| SVK råa | 4488 |
| SVK efter dedup på koord | 4411 (-77 dubbletter som "Trons kapell Mo") |
| OSM (place_of_worship + building=church) | 5206 |
| Matchade | 3433 |
| Bara SVK | 978 |
| Bara OSM | 1773 |
| Matchade m. namn-mismatch | 80 |
| Matchade >50 m | 95 |
| Matchade m. OSM-taggbrist | ~418 |

## Datakällor

**SVK Platser**: `?is=churchandchapel`, hämtar alla 4488 kyrkor och
kapell direkt från `api.svenskakyrkan.se/platser/v4/place` med APIKEY
som query-param. (Tidigare gick allt via dev-proxyn pga rapporterade
500-fel - de syns inte längre, gateway-bug eller policy-ändring som
fixats. Proxy-vägen finns kvar via `PLATSER_BASE`-env för lokal körning
utan att exponera nyckeln.)

**OSM via Overpass**: kombinerat filter
`[amenity=place_of_worship][religion=christian]` PLUS
`[building=church|chapel]` inom Sverige. Building-filtret behövs
eftersom många kyrkbyggnader saknar `amenity`-taggen i OSM (exempel:
Ramsjö kyrka var bara taggad som `building=church`, inte
`amenity=place_of_worship`).

## Algoritm

`build_diff.py` gör följande:

1. **Dedup SVK på koordinat**: SVK-poster på exakt samma punkt
   (5-decimaler precision = 1 m) sammanslås. Behåller den med högsta
   prioritet enligt `_name_priority` (suffix `kyrka` > `kapell` > övrigt).
   Tar bort 77 dubbletter som "Annan plats Mo", "Trons kapell Mo" etc.
2. **Reprojicera** båda källors koordinater från WGS84 till SWEREF
   99 TM (EPSG:3006) så avstånd kan mätas i meter.
3. **Bygg STRtree** över OSM-punkterna.
4. **Greedy global matchning**: bygg lista av alla SVK-OSM-par inom
   radien, sortera på `(distance, -namnlikhet)`, plocka kortaste först
   med tie-break på högsta namn-likhet. Hindrar att två SVK-poster
   på samma koord kapar OSM-pinnen från den med bättre namn-match.
5. **Klassificera matched** som namn-mismatch (similarity < 0.55 efter
   normalisering), avstånd >50 m, eller OSM-taggbrist (saknar
   `amenity`, `religion=christian` eller en SvK-denomination).

## Filer

```
osm-konsistenscheck/
  build_svk.py      # hämtar SVK Platser direkt med APIKEY (PLATSER_BASE för proxy)
  build_osm.py      # hämtar OSM via Overpass (med retry mot 3 spegelservrar)
  build_diff.py     # matchar och skriver diff.geojson + summary
  rebuild.sh        # kör de tre stegen i ordning (kräver att servern kör)
  index.html        # Leaflet-karta med kluster, filter, sök, export, rebuild-knapp
  data/             # gitignored
    svk_kyrkor.geojson
    osm_kyrkor.geojson
    diff.geojson
    diff_summary.json   # innehåller built_at + svk_source_at + osm_source_at
```

In-app-rebuild-endpointarna lever i `scripts/serve.py` (single-threaded
HTTPServer, jobbet körs i en `threading.Thread(daemon=True)` så den inte
blockerar status-pollningen).

## Möjliga framtida tillägg

- **Wikidata-cross-check**: för osm_only med wikidata-tagg, slå upp
  Wikidata och se om det är en "Church of Sweden church" - då är det
  förmodligen en miss i SVK Platser, inte annan denomination.
- **Per-nod tag-copy**: knapp i popupen som kopierar de saknade
  taggarna (t.ex. `amenity=place_of_worship\nreligion=christian`) till
  clipboard. Användaren öppnar iD via "Redigera"-länken som vanligt och
  klistrar in i "Alla taggar"-vyn. Manuellt verifierat per nod, inom
  OSM:s riktlinjer (ej massimport).
- **Per-stift-statistik**: var i landet är diskrepansen störst?
- **Slug-baserade länkar för svk_only**: vissa svk_only saknar slug
  i nuvarande hämtning - lägg till om det blir aktuellt.
