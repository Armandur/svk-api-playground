# svk-api-playground

Lekplats och dokumentationskälla för Svenska kyrkans publika API:er.

## Dokumentation

Öppna `docs/svk-apis.html` i en webbläsare. Single-page docs med
sidebar-nav genererad från `docs/modules/*.md`.

```bash
# Allt i ett: watcher + server (Ctrl+C avslutar båda)
./start.sh                          # http://localhost:8088/

# Eller var för sig:
uv run scripts/serve.py             # bara servern
uv run scripts/build_docs.py        # engångsbygge
uv run scripts/watch_docs.py        # bara watchern (rebuild + sync)
```

Källan ligger i `docs/modules/` - en fil per API plus några
gemensamma sektioner (`_overview.md`, `_quickref.md`, `_brand.md`,
`_deprecated.md`, `_todo.md`).

## Struktur

Se [`CLAUDE.md`](CLAUDE.md) för full beskrivning av repo-layout och hur
docs uppdateras.

## Pilot-projekt

Pilot-projekt mot API:erna läggs som undermappar i denna repo. Idéer
finns i `docs/modules/_todo.md`:

- `kbr-tidslinje/` - animerad karta över ~3 500 kyrkobyggnader 1000-idag
- `kbr-kvalitet/` - datakvalitetsrapport för KBR, jämför mot Platser och OSM
- `osm-konsistenscheck/` - SVK Platser ↔ OSM-jämförelse, dygnsfärsk diff
- `forsamlingsindelning-historik/` - församlings- och pastoratsgränser 2008-2026
- `forsamlingskarta-enklaver/` - enklaver och exklaver i församlingar
- `forsamlingskarta-leaflet/` - klickbar Leaflet-karta över alla församlingar
- `ls-visualize/` - karta över Löneservice-anslutning per ekonomisk enhet
- `signage-platser/` - signage-vy med dynamiska öppettider
- `platser-edit-app/` - mini-app för platsadministration
- `kyrkoaret-widget/` - kyrkoårs-widget för embed
- `unit-api/` - sökbar lista och CSV-export av ekonomiska enheter
- Församlingssök-formulär, kalenderhändelse-aggregator (planerade)

## Live-deploys

Byggs dagligen 04:00 UTC av `.github/workflows/pages-deploy.yml` och
publiceras under <https://armandur.github.io/svk-api-playground/>:

- **osm-konsistenscheck** - SVK ↔ OSM-jämförelse, dygnsfärsk diff
- **kbr-tidslinje** - animerad karta över ~3 500 kyrkobyggnader 1000-idag
- **forsamlingsindelning-historik** - församlingsgränser 2008-2026
- **forsamlingskarta-enklaver** - enklaver och exklaver bland församlingar
- **ls-visualize** - Löneservice-anslutning per ekonomisk enhet
- **unit-api** - sökbar lista över ekonomiska enheter
- **signage-platser** - signage-demo med Härnösands domkyrka
- **kyrkoaret-widget** - kyrkoårs-widget med dagens högtid
- **PDF-bokhylla** - Kyrkoordningen, alla SvKB och biskopsbrev som statisk
  3D-bokhylla med inbyggda läsare

Cache används flitigt: data som ändras sällan (t.ex. shapefiles per
år) återanvänds mellan körningar och byggs bara om vid script-ändring.

## Autentisering

De flesta tjänsterna kräver en SVK-API-nyckel som skickas som
`?apikey=` eller header `SvkAuthSvc-ApiKey`. Skaffas via
`https://api.svenskakyrkan.se/`.

CalendarAPI ligger på Azure APIM och använder `Ocp-Apim-Subscription-Key`
istället. Se `docs/modules/_overview.md`.
