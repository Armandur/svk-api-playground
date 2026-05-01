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

- Signage-vy med dynamiska öppettider (Härnösands domkyrka m.fl.)
- Mini-app för platsadministration som alternativ till Content Studio
- Kyrkoårs-widget för embed på församlings-hemsidor
- Församlingssök-formulär
- Kyrkokarta i webbläsaren med Leaflet
- Kalenderhändelse-aggregator för stiftskalender

## Autentisering

De flesta tjänsterna kräver en SVK-API-nyckel som skickas som
`?apikey=` eller header `SvkAuthSvc-ApiKey`. Skaffas via
`https://api.svenskakyrkan.se/`.

CalendarAPI ligger på Azure APIM och använder `Ocp-Apim-Subscription-Key`
istället. Se `docs/modules/_overview.md`.
