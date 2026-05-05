# unit-api

Demo + CSV-export av Svenska kyrkans ekonomiska enheter (stift +
pastorat + jure-egna församlingar) från UnitAPI.

## Stack

- **Bygg-skript**: `fetch_ekonomiska_enheter.py` (Python 3.12, uv-inline-deps).
  Hämtar alla 2 220 enheter via OData-paginering ($top=1000), filtrerar
  klientside till de 596 ekonomiska + Trossamfundet, skriver
  `data/ekonomiska_enheter.csv` och `data/ekonomiska_enheter.json`.
- **Frontend**: enkel `index.html` (vanilla HTML/CSS/JS). Läser direkt
  från statiska `data/ekonomiska_enheter.json`-filen - ingen proxy
  behövs så sidan fungerar även på GitHub Pages.

## Filer

- `fetch_ekonomiska_enheter.py` - bygg-skript, kräver APIKEY_PROD.
- `index.html` - hela vyn (HTML + CSS + JS inline).
- `data/ekonomiska_enheter.csv` - två kolumner (enhetsnamn, stift),
  UTF-8 BOM, `;` som delimiter. Användar-export.
- `data/ekonomiska_enheter.json` - full data med `unitType`, `stift`,
  `isItf`, `isOvrig`. UI:t läser denna.

## Hårdkodade specialfall

`fetch_ekonomiska_enheter.py` har tre listor som inte kan utläsas
från API:t:

- `TROSSAMFUNDET_UNIT_ID = 1` - "Kyrkokansliet - Ägarweb" i UnitAPI,
  men organisatoriskt motsvarar det Trossamfundet Svenska kyrkan på
  riksnivå. Vi byter namn vid presentation.
- `ITF_UNIT_IDS` - de 5 erkända icke-territoriella församlingarna.
  Inga API-fält skiljer dem; hårdkodad lista enligt SVK:s officiella
  förteckning.
- `OVRIG_UNIT_IDS` - samfälligheter som inte är vanliga pastorat
  (Göteborgs begravningssamfällighet, Samfälligheten Gotlands kyrkor).

## Pages-deploy

`fetch_ekonomiska_enheter.py` körs i `pages-deploy.yml` med
`APIKEY_PROD` som secret. Producerar både CSV och JSON som kopieras
till `_deploy/unit-api/data/`.

## UnitAPI-begränsningar att tänka på

- Max `$top=1000` - paginera med `$skip` (3 anrop för 2 220 enheter).
- `$filter` på `unitType` med åäö är trasigt (Latin-1-bugg på
  servern) - filtrera klientside.
- `unitType=Sammfällighet` är felstavat (två m). Klienter måste
  matcha den felaktiga formen tills SVK åtgärdat det.

Se [`../docs/modules/UNITAPI.md`](../docs/modules/UNITAPI.md) för full
referens.
