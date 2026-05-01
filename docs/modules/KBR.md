# Kyrkobyggnadsregistret (KBR API)

REST-inspirerat API över byggnader (kyrkor + övriga byggnader) och
begravningsplatser ur Kyrkobyggnadsregistret.

## Snabbfakta

| Fält | Värde |
|---|---|
| Stil | REST (JSON eller XML via `Accept`) |
| Bas-URL prod | `https://api.svenskakyrkan.se/kbr/api/` |
| Bas-URL test | `https://api-t.svenskakyrkan.se/kbr/api/` |
| Version | v1 |
| Auth | `?apikey=` eller `SvkAuthSvc-ApiKey: <key>` |
| Doc | https://api.svenskakyrkan.se/doc/kyrkobyggnadsregistret/index.html |
| Verifierad | ✓ prod 2026-05-01 (Linköpings domkyrka, byggnad/32555 - invigd 1296, treskeppig kalkstensbyggnad) |

## Resurser

| Path | Funktion |
|---|---|
| `GET /byggnader` | Lista byggnader (kyrkor + övriga) |
| `GET /byggnad/{id}` | En byggnad på KBR-id (IdentitySVK) |
| `GET /begravningsplatser` | Lista begravningsplatser |
| `GET /begravningsplats/{id}` | En begravningsplats |

**OBS** Resursen heter `byggnader` (lista) men `byggnad` (singular). Båda
typerna (Kyrkor + Övriga byggnader) finns under `/byggnader` - separera
med `?kyrka=true|false`.

## Query-parametrar (gäller båda resurslistorna)

### Field selection

| Param | Funktion |
|---|---|
| `fields=*` | Alla fält |
| `fields=namn,id,pastorat` | Specifika fält |
| `fields=` saknas | Default = grundfält (`namn`, `id`) |

### Paging

| Param | Default | Range |
|---|---|---|
| `limit=N` | 10 | 3-100 |
| `offset=N` | 0 | - |

### Sortering

`orderby=<fält>` (suffix `-` för fallande, t.ex. `orderby=namn-`).

### Filter

| Param | Exempel | Funktion |
|---|---|---|
| `kyrka=true\|false` | `kyrka=true` | Bara kyrkor / bara övriga |
| `namn=<str>` | `namn=linköpings domkyrka` | Exakt namn (URL-encoda mellanslag) |
| `namn=~<str>` | `namn=~mora` | Innehåller (matchar `Hedemora`, `Bollmora`...) |
| `namn=^<str>` | `namn=^mora` | Börjar med |
| `id=N,N,N` | `id=34368,32555,32494` | Flera id-träffar |
| `andraddatum=YYYYMMDD-` | `andraddatum=20240101-` | Från datum |
| `andraddatum=YYYYMMDD-YYYYMMDD` | `andraddatum=20131201-20131231` | Intervall |
| `skapaddatum=...` | dito | Skapelsedatum |
| `agandeenhet=<namn>` | `agandeenhet=~linköping` | Ägare (stöder `~`/`^`) |
| `agandeenhetlkf=N,N` | `agandeenhetlkf=058001,058033` | Ägare per LKF-kod |
| `nuvarandefunktion=~kapell` | dito | Funktion (stöder `~`/`^`) |
| `testdata=true` | - | Returnerar fullt fältexempel mot testmiljön |

## Curl-exempel

```bash
export APIKEY='din-svk-api-nyckel'
BASE='https://api.svenskakyrkan.se/kbr/api'

# Linköpings domkyrka (id 32555) med alla fält
curl -s "${BASE}/byggnad/32555?fields=*&apikey=${APIKEY}" | jq

# Första 20 kyrkorna med utvalda fält
curl -s "${BASE}/byggnader?kyrka=true&limit=20&fields=namn,id,pastorat,stift&apikey=${APIKEY}" | jq

# Sök byggnader vars namn börjar med "mora"
curl -s "${BASE}/byggnader?namn=^mora&apikey=${APIKEY}" | jq

# Byggnader ändrade efter 2024-01-01
curl -s "${BASE}/byggnader?andraddatum=20240101-&fields=namn,id,andraddatum&apikey=${APIKEY}" | jq

# Alla kapell
curl -s "${BASE}/byggnader?nuvarandefunktion=~kapell&fields=namn,nuvarandefunktion&limit=100&apikey=${APIKEY}" | jq

# Begravningsplatser i Linköpings kommun (058033 = Linköping)
curl -s "${BASE}/begravningsplatser?agandeenhetlkf=058033&fields=*&apikey=${APIKEY}" | jq

# Hämta ren testdata för att se fullständig fältstruktur
curl -s "https://api-t.svenskakyrkan.se/kbr/api/byggnader?fields=*&testdata=true&apikey=${APIKEY}" | jq '.[0]'
```

## Felkoder

Standard HTTP, men body innehåller förklaring vid 400:

| Kod | Betydelse |
|---|---|
| 200 | OK, resultatet i body (JSON eller XML beroende på `Accept`) |
| 400 | Bad Request - body med felförklaring, t.ex. `{"message":"Otillåtet värde för byggnadsid! ..."}` |
| 401 | Unauthorized - saknad eller fel API-nyckel |
| 404 | Not Found - resurs med givet id finns inte |
| 500 | Internt serverfel - vänta och försök igen |

## Datastruktur

Två typer under `/byggnader`:

- **Kyrkor** - alla basfält + extrafält (arkitekt, byggår, kulturklassning,
  innehåll i kyrkorum, etc).
- **Övriga byggnader** - bara basfält.

En byggnad **kan byta typ** via redigering i KBR - därför samma path för
båda. Begravningsplatser har ett enhetligt fältset.

### Multipla värden i fält

Vissa fält tillåter flera värden separerade med `|` (pipe):

- `AnnanAnvändning`
- `AnpassningAnnanAnvandning`

Båda gäller för Byggnader-resursen.

### Fält-introspektion

```bash
# Hämta default-fält
curl -s "${BASE}/byggnader?limit=1&apikey=${APIKEY}" | jq '.[0] | keys'

# Hämta full fält-uppsättning från testdata
curl -s "https://api-t.svenskakyrkan.se/kbr/api/byggnader?fields=*&testdata=true&apikey=${APIKEY}" \
  | jq '.[0] | keys'
```

## Användningsfall

- Visa info om kyrkobyggnaden för en besökare på församlingens hemsida.
- Bygg upp register över skyddsvärda kyrkor och deras inventarier.
- Geografisk analys av kyrkobyggnader (i kombination med Platser/Församlingskartor).
- Underhållsplanering ("vilka byggnader är ändrade senaste året?").
