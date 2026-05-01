# CalendarAPI

Konsoliderar kalenderhändelser från Svenska kyrkans olika källor till
en gemensam REST-tjänst. Stöd för återkommande händelser ("event
collections"), fulltext, partial patch och historik per event.

## Snabbfakta

| Fält | Värde |
|---|---|
| Stil | REST (JSON), Azure API Management |
| Server-URL | `https://svk-apim-prod.azure-api.net/calendar/v1` |
| OpenAPI-spec (lokal) | [`docs/specs/calendarapi.openapi.json`](../specs/calendarapi.openapi.json) - 376 KB, OpenAPI 3.0.1 |
| Version (changelog) | v1.2 (per 2023-10-06 [1.0.3]) |
| Plattform | Azure APIM (`svk-apim-prod`) |
| Auth (läs/skriv) | `Ocp-Apim-Subscription-Key: <key>` (header) eller `?subscription-key=<key>` (query) |
| OAuth2 | För skrivande operationer - token från `/test/oauth2/token` |
| Doc | https://svk-apim-prod.developer.azure-api.net/api-details#api=calendarapi |
| Verifierad | ✓ prod 2026-05-01 (event-search, both auth-forms) |

> **OBS:** `https://api.svenskakyrkan.se/calendar/v1` finns men är en
> **separat ingress** som inte accepterar Azure subscription-keys.
> Returnerar `401 "Subscription is required"`. Använd Azure-gateway-domänen
> `svk-apim-prod.azure-api.net` för att nå CalendarAPI.

## Operations - 8 paths, 15 operations

| Method | Path | Funktion |
|---|---|---|
| GET | `/event/{id}` | Hämta enskilt event |
| PUT | `/event/{id}` | Skriv över befintligt event |
| PATCH | `/event/{id}` | Partiell uppdatering |
| DELETE | `/event/{id}` | Ta bort event |
| GET | `/event/{id}/history` | Pagerad historik per event |
| GET | `/event/search` | Sök events (queryparams) |
| POST | `/event/search` | Sök events (body, för stora frågor) |
| PUT | `/event` | Skapa eller upserta event |
| DELETE | `/event/by-query` | Ta bort events som matchar query |
| PATCH | `/event/by-query` | Patch events som matchar query |
| GET | `/eventcollection/{collectionid}` | Hämta alla events i kollektion |
| POST | `/eventcollection/{rule}` | Skapa eller testa återkommande events |
| DELETE | `/eventcollection/{collectionid}` | Ta bort kollektion |
| GET | `/test/oauth2/token` | Hämta access-token (test) |
| POST | `/test/oauth2/token` | Hämta access-token (test) |

## GET /event/search - parametrar

| Param | Typ | Funktion |
|---|---|---|
| `q` | string | Fulltext (söker i titel, description och performer-namn) |
| `from`, `to` | string (datetime) | Tidsfönster - events som startar efter `from` eller är aktiva vid tidpunkten / slutar före `to` etc |
| `duration` | string | Events som slutar/är aktiva inom relativ tidsperiod |
| `start`, `end` | string | Range-filter på `Event.Start` / `Event.End` (t.ex. `start=2026-05-01..2026-05-31`) |
| `place_id` | string | "Is any of" - events på en av angivna platser (kommaseparerat) |
| `owner_id` | string | "Is any of" - ägande enheter (kommaseparerat) |
| `owner_producerId`, `owner_sourceId` | string | Filter på producent/källa |
| `categories_id`, `tags_id` | string | "Is any of" - kategorier/taggar |
| `is` | string | "Is of type" - filtrera på event-typ |
| `attendanceMode` | string | "Is any of" |
| `access` | string | `External` eller `Internal` |
| `collectionid` | string | "Is any of" |
| `title`, `description`, `additionalId`, `id` | string | Strängfilter (`is`/`is-not`/`starts-with`/`contains`) |
| `updated`, `deleted` | string | Range-filter på datum-fält |
| `include` | string | Komma-separerad: `deleted` m.fl. |
| `expand` | string | Komma-separerad metadata att expandera |
| `limit` | int32 | Max antal items |
| `continuation` | string | Pagineringstoken |

## Sökresponsens format (verifierat)

```jsonc
{
  "limit": 5,
  "next": "https://svk-apim-prod.azure-api.net/calendar/v1/event/search?...&continuation=...",
  "continuation": "<base64-token>",
  "result": [ /* APIEvent[] */ ],
  "status": 200,
  "traceId": "00-...",
  "instanceName": "prod1"
}
```

Event-arrayen ligger i `result` (inte `events` eller `results`). Följ
`next`-länken med GET för paginering.

## Verifierat exempel

```jsonc
{
  "id": "dbcbb0d723cf48f9afc1040615289857",
  "additionalId": "397237220",       // producentens externa id
  "owner": {
    "producerId": "25a6850a-5146-4302-8793-8331fa11dfc7",
    "sourceId":   "46bcc1a2-3c9e-4fb7-8e79-152c20c17543",
    "id": "2426"                     // unitId i UnitAPI
  },
  "title": "Digitalt bibelsamtal",
  "description": "Varannan tisdag (udda veckor) ses vi på Zoom...",
  "start": "2026-01-13T19:00:00+01:00",
  "end":   "2026-06-02T20:15:00+02:00",
  "startLocalTime": { "offset": "+01:00", "date": "2026-01-13", "time": "19:00:00" },
  "endLocalTime":   { "offset": "+02:00", "date": "2026-06-02", "time": "20:15:00" },
  "isFullDayEvent": false,
  "access": "External",
  "attendanceMode": { "offline": {} },   // one-of: offline / online / mixed
  "contact": { "consentGiven": true },
  "created": "2025-12-17T16:43:05.4295214+01:00",
  "updated": "2026-01-15T15:50:15.9816356+01:00"
}
```

`attendanceMode` är ett "one-of"-objekt (likt `placeTypes` i Platser):
exakt en nyckel är aktiv (`offline`, `online`, `mixed`).

## Event-modellen

Från `docs/specs/calendarapi.openapi.json`. Topp-fält:

| Fält | Typ | Anteckning |
|---|---|---|
| `id` | string | UUID, sätts av servern |
| `additionalId` | string? | Producentens egna ID (för synk från externa system) |
| `collectionId` | string? | Refererar event-kollektion (om del av återkommande serie) |
| `owner` | `EventOwner` | Producent + ägande enhet |
| `title` | string | Titel |
| `description` | string? | Beskrivning |
| `start`, `end` | datetime | UTC enligt RFC 3339 |
| `timeZoneId` | string? | T.ex. `Europe/Stockholm` |
| `isFullDayEvent` | boolean | Heldagsevent |
| `access` | `EventAccessEnum` | `External` (publikt) eller `Internal` |
| `attendanceMode` | `AttendanceMode` | T.ex. fysisk/online/hybrid |
| `performers` | `Performer[]?` | Förkunnare/medverkande |
| `contact` | `EventContact` | Kontaktinfo för eventet |
| `links` | `Link[]?` | Relaterade länkar |
| `place` | `PlaceInfo` | Refererar Platser-API:t (`placeId`) |
| `categories` | `Category[]?` | Refererar Ämnesområden |
| `tags` | `Tag[]?` | Refererar Ämnesområden |
| `eventType` | `EventType` | T.ex. Gudstjänst, Konsert, Bibelstudie |
| `created`, `updated` | datetime | Timestamps |
| `createdBy`, `updatedBy` | string? | Användare |
| `deleted`, `deletedBy` | datetime? / string? | Logiskt borttagning |

`APIEvent` är `Event` + `startLocalTime`, `endLocalTime` (renderad lokal
tidsrepresentation för klienter).

### `EventAccessEnum`

`External` (publikt synligt) eller `Internal` (intern - kräver auth-roll
för att se).

## Curl-exempel

```bash
export AZURE_KEY='din-azure-apim-subscription-key'
BASE='https://svk-apim-prod.azure-api.net/calendar/v1'

# Sök events med fulltext
curl -s "${BASE}/event/search?q=gudstjänst&limit=5" \
  -H "Ocp-Apim-Subscription-Key: ${AZURE_KEY}" | jq

# Tidsbaserad sökning
curl -s "${BASE}/event/search?from=2026-05-01&to=2026-05-31&access=External&limit=20" \
  -H "Ocp-Apim-Subscription-Key: ${AZURE_KEY}" | jq

# Hämta enskilt event
curl -s "${BASE}/event/<uuid>" \
  -H "Ocp-Apim-Subscription-Key: ${AZURE_KEY}" | jq

# Hämta historik (pagerad)
curl -s "${BASE}/event/<uuid>/history" \
  -H "Ocp-Apim-Subscription-Key: ${AZURE_KEY}" | jq

# Hämta alla events i en återkommande kollektion
curl -s "${BASE}/eventcollection/<collectionid>" \
  -H "Ocp-Apim-Subscription-Key: ${AZURE_KEY}" | jq

# OAuth2 token för skrivande operationer
curl -s -X POST "${BASE}/test/oauth2/token" \
  -H "Ocp-Apim-Subscription-Key: ${AZURE_KEY}" \
  -d 'grant_type=client_credentials&client_id=...&client_secret=...'

# Sök via management-API (utan auth - bara metadata)
curl -s 'https://svk-apim-prod.management.azure-api.net/subscriptions/000/resourceGroups/000/providers/Microsoft.ApiManagement/service/svk-apim-prod/apis/calendarapi/operations?api-version=2022-04-01-preview&$top=200' | jq
```

## Beteenden och regler

- **Auto-undelete:** Borttagna events undeleteas automatiskt vid uppdatering
  (breaking change 2023-10-06). Opt-out finns per endpoint - läs spec:en.
- **Lost-update-skydd:** `If-Unmodified-Since`-header stöds vid
  single-update.
- **Search:** Stränguppslag stöder **inte wildcards** sedan 2023-09-04 -
  använd `q` för fulltext (söker även på performer-namn).
- **Paging:** `next`-länkar i sökresultat ska alltid följas med GET
  (även om sökningen var POST).
- **Field-typing:** `is`/`is-any-of` stöder null/not-null. `EventType`
  får vara null sedan 2023-05-10.

## Referenser till andra tjänster

| Fält i Event | Tjänst |
|---|---|
| `place.id` | [PLATSER](#PLATSER) (`/place/{id}`) |
| `owner.id` | [UNITAPI](#UNITAPI) (`/units(id)`) |
| `categories[].id`, `tags[].id` | [AMNESOMRADEN](#AMNESOMRADEN) |

Alla referenser **valideras** vid skrivning - en ogiltig `place.id` ger
4xx.

## Caveats

- Krav på giltig OAuth2-registrering för alla producerande klienter.
- `Performers` är sedan 2023 en lista av enkla objekt (inte längre
  stora unit-refs).
- Söker man på `id` som sträng tillåts det (sedan 2023-09-18).
- Använd `additionalId` för att lagra externa system-id:n stabilt
  (egna `id` ändras inte men kan inte styras).

## Nästa steg

- Skaffa Azure APIM subscription-key för tester.
- Verifiera servern - prova både Azure-gateway-URL:en och
  `api.svenskakyrkan.se/calendar/v1` för att se om båda fungerar.
- Bygg en POC som hämtar events för en stiftskalender (filtrera på
  `owner_id` för stiftens enheter).
