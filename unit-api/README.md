# unit-api

Demo och CSV-export av Svenska kyrkans **ekonomiska enheter** -
enheter med egen ekonomi: stift, pastorat (samfälligheter) och
församlingar med egen ekonomi (jure egna).

Fungerar både som:

- **Webbsida** som listar alla 596 + Trossamfundet, grupperade per
  stift, med sök och typ-filter. Special-badges för icke-territoriella
  församlingar (ITF) och övriga samfälligheter.
- **CSV-export** med två kolumner (enhetsnamn, stift) som kan användas
  för diarieföring eller massutskick.

## Kör

```bash
# Bygg data (skriver data/ekonomiska_enheter.csv + .json):
uv run fetch_ekonomiska_enheter.py

# Servera webbsidan via repo-roten:
./../start.sh                # http://ubuntu-ai:8088/unit-api/
```

`fetch_ekonomiska_enheter.py` läser `APIKEY_PROD` (eller `APIKEY_TEST`)
från `../.env` eller miljön. Sidan läser sedan den statiska
`data/ekonomiska_enheter.json`-filen direkt - ingen proxy behövs.

## Datamodell

| Fält | Typ | Anteckning |
|---|---|---|
| `unitId` | int | Från UnitAPI |
| `name` | string | Enhetens namn |
| `unitType` | string | `Stift` / `Sammfällighet` / `FörsamlingE` / `Trossamfund` |
| `stift` | string | Stiftnamn (eller "Nationell nivå" för Trossamfundet) |
| `isItf` | bool | Icke-territoriell församling |
| `isOvrig` | bool | Övrig samfällighet (inte vanligt pastorat) |

## Specialfall

- **Trossamfundet Svenska kyrkan** finns inte som namngiven enhet i
  UnitAPI. Vi inkluderar `unitId=1` "Kyrkokansliet - Ägarweb" och
  byter dess namn vid presentation. Stift-tillhörigheten är
  "Nationell nivå".
- **Icke-territoriella församlingar (ITF)**: Hovförsamlingen,
  Tyska S:ta Gertruds, Finska församlingen, Karlskrona
  Amiralitetsförsamling, Tyska Christinae. Hårdkodad lista i
  `fetch_ekonomiska_enheter.py` eftersom inget API-fält identifierar
  dem. Endast 4 av 5 har `unitType=FörsamlingE` - Tyska Christinae
  hör till ett pastorat och är därför inte med i exporten.
- **Övriga samfälligheter**: Göteborgs begravningssamfällighet,
  Samfälligheten Gotlands kyrkor. Markeras med "Övrig"-badge.

## CSV-format

UTF-8 med BOM, `;` som delimiter (Excel-kompatibelt). Två kolumner:
enhetsnamn och stift.

```csv
﻿Adolf Fredriks församling;Stockholms stift
Alfta-Ovanåkers församling;Uppsala stift
Trossamfundet Svenska kyrkan;Nationell nivå
...
```

## Dokumentation

Se [`../docs/modules/UNITAPI.md`](../docs/modules/UNITAPI.md) för
fullständig referens av OData-API:t.
