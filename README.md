# svk-api-playground

Lekplats och dokumentationskälla för Svenska kyrkans publika API:er.

## Dokumentation

Öppna `docs/svk-apis.html` i en webbläsare. Single-page docs med
sidebar-nav genererad från `docs/modules/*.md`.

```bash
# Bygg om dokumentationen
uv run scripts/build_docs.py

# Eller watch-läge under redigering
uv run scripts/watch_docs.py
```

Källan ligger i `docs/modules/` - en fil per API plus några
gemensamma sektioner (`_overview.md`, `_quickref.md`, `_deprecated.md`,
`_todo.md`).

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
