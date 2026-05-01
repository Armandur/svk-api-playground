# Platser

REST-API för platser i Svenska kyrkans verksamhet (kyrkor, församlingshem,
kapell, kanslier, begravningsplatser m.m.). Refereras från CalendarAPI
för `placeId`. **Innehåller strukturerade öppettider per plats** -
kärnan i signage-projektet.

## Snabbfakta

| Fält | Värde |
|---|---|
| Stil | REST (JSON in/ut), HTTP-standardverb |
| Bas-URL prod | `https://api.svenskakyrkan.se/platser/v4` |
| Bas-URL test | `https://api-t.svenskakyrkan.se/platser/v4` (endast inom kyrknätet) |
| Version | v4 aktiv (4.1.0 unreleased), v3 fryst |
| Auth | `?apikey=` eller `SvkAuthSvc-ApiKey: <key>` (utan = 403) |
| Doc | `/doc/` (intro), `/doc/api/index` (datamodell), `/doc/api/search` (sök) |
| Datum-format | ISO 8601, exponeras som `YYYY-MM-DDTHH:mm:ss.fffffZ` |
| Geo | GeoJSON 2016, WGS84, ordning **lon, lat** |
| Tidszon för öppettider | Platsens lokala tidszon (implicit) |
| Verifierad | ✓ prod 2026-05-01 (efter villkorsacceptans) |
| Total platser | 9474 |

## Endpoints

| Method | Path | Funktion | Svarskod |
|---|---|---|---|
| GET | `/place` | Sök/lista (returnerar `{totalHits, results: Place[]}`) | 200 |
| GET | `/place/{id}` | Hämta enskild plats på UUID | 200 / 404 |
| PUT | `/place` | Skapa ny plats | 201 (Location-header) |
| PUT | `/place/{id}` | Skriv över befintlig plats | 200 |
| PATCH | `/place/{id}` | Partiell uppdatering | 204 (Location-header) / 404 |
| DELETE | `/place/{id}?deletedby=<user>` | Logiskt borttagning | 204 / 400 (saknar `deletedby`) |
| GET | `/placetype` | Lista alla möjliga platstyper (sträng-array) | 200 |

**Viktigt:** `/place/{slug}` fungerar **inte** - använd UUID, inte slug
för enskild GET. Slug:en är inte permanent (ändras när platsens namn
ändras).

## Sökparametrar (GET /place)

Alla mot `/place?...`:

| Param | Funktion |
|---|---|
| `q=<text>` | Fulltext (söker i alla fält, kan kombineras med explicita filter) |
| `is=<type>[,<type>...]` | Filtrera på platstyper, t.ex. `is=churchandchapel,secretariat` |
| `name=<str>` / `~<str>` / `^<str>` | Namn (exakt / innehåller / börjar med) |
| `nearby=<lon>,<lat>&nearbyRadius=<m>` | Geosök, radie i meter (WGS84) |
| `placedetails_hastoilet=true` | Boolean på underfält (snake_case path) |
| `owner_id=<id>`, `owner_type=Församling` | Filter på ägare |
| `deleted=true` | Inkludera borttagna |
| `offset=N`, `limit=N` | Paginering (default 100, max 500) |
| `orderby=<fält>[-]` | Sortering (kommaseparerade fält, `-` suffix = fallande) |
| `test=true` | Hårdkodat testdata med alla fält ifyllda - **format `{count, hits}`** istället för `{totalHits, results}` |

Vanligt sök-svar:

```jsonc
{ "totalHits": 9474, "results": [ /* Place[] */ ] }
```

Testdata-svar (`?test=true`):

```jsonc
{ "count": 1, "hits": [ /* Place[] */ ] }
```

Sökexempel från doc:en:

```
GET /place?
    deleted=
    &is=churchandchapel,secretariat
    &name=~otkyrk
    &q=sjöutsikt
    &placedetails_hastoilet=true
    &nearby=17.123,59.22&nearbyRadius=2500
```

## Datamodell - `Place`

Topp-fält (verifierat 2026-05-01 mot prod):

```jsonc
{
  "id": "uuid",                       // tvingande, sätts vid skapande, anges aldrig
  "slug": "20270-...",                // unik men icke-permanent (regenereras vid namnbyte)
  "parent": { "id": "uuid", "name": "..." },  // tom om ingen förälder
  "name": "Härnösands domkyrka",      // tvingande
  "shortDescription": "...",          // bara text, ingen formattering
  "longDescription": "...",           // ev. markdown (TBD)
  "owner": {
    "id": "20270",                    // matchar enhetsid i andra API:er
    "name": "Härnösands domkyrkoförsamling",
    "type": "Församling"              // även "Sammfällighet", "Pastorat", "Projekt" m.fl.
  },
  "geolocation": {                    // GeoJSON Feature
    "type": "Feature",
    "geometry": { "type": "Point", "coordinates": [lon, lat] }   // WGS84!
  },
  "geolocationInfo": {                // beräknas auto från geolocation
    "lkf": "228001", "county": "Västernorrlands län",
    "municipality": "Härnösands Kommun", "city": "", "localArea": "",
    "country": "SE"
  },
  "contactInfo": {
    "phone": { "countryCode": 0, "areaCode": 0, "number": 0 },
    "email": "...", "url": "...",
    "fetchAutomatically": false       // true => hämtar ägar-enhetens kontaktinfo dynamiskt
  },
  "visitingInfo": { "address": "", "postalCode": "", "city": "", "description": "" },
  "openHours": { /* se nedan */ },
  "categories": [{ "id": "uuid", "name": "..." }],   // refererar Ämnesområden categories
  "tags": [{ "id": "uuid", "name": "..." }],          // refererar Ämnesområden tags
  "placeDetails": { /* se nedan */ },
  "placeTypes": { /* se nedan */ },
  "media": { "audio": [], "video": [], "images": [], "links": [] },
  "created": "iso", "createdBy": "user***",
  "updated": "iso", "updatedBy": "user***",
  "published": "iso", "publishedBy": "user***",
  "depublished": "iso", "depublishedBy": "user***",
  "deleted": "iso", "deletedBy": "user***"
}
```

`***` = fält endast synliga för anropare med särskild rättighet.

## openHours - schema

**OBS:** I doc:en beskrivs `openHours` som direkt array, men i alla
verkliga svar (både live och testdata) är det ett objekt med
`info?` + `periods: []`:

```jsonc
{
  "openHours": {
    "info": "Valfri fritextkommentar",
    "periods": [
      {
        "validFrom": "2022-03-17",       // ISO date eller null/saknas (=första)
        "validTo": "2023-08-15",         // ISO date eller null/saknas (=sista, "tills vidare")
        "days": {
          "mo": [{"from": "08:00", "to": "16:00"}],
          "tu": [], "we": [], "th": [], "fr": [], "sa": [], "su": []
        }
      }
    ]
  }
}
```

- Veckodagsnycklar: `mo, tu, we, th, fr, sa, su` (engelska 2-bokstävers).
- **Lista per dag** = flera intervall stöds (t.ex. lunchstängt
  `[{"from":"08:00","to":"12:00"},{"from":"13:00","to":"16:00"}]`).
- **Tom/saknad array** = stängt den dagen.
- **Säsongsperioder** - flera period-objekt med olika `validFrom/validTo`.
- Tider implicit i platsens lokala tidszon.
- Schema är löst baserat på [schema.org OpeningHoursSpecification](https://schema.org/OpeningHoursSpecification).

## placeTypes - enum

Exakt en typ är aktiv åt gången. Övriga är inte med i svaret.

| Nyckel | Beskrivning | Egna fält |
|---|---|---|
| `churchAndChapel` | Kyrkor och kapell | - |
| `parishHome` | Församlingshem | - |
| `secretariat` | Kansli | - |
| `cemetery` | Begravningsplats | - |
| `external` | Extern (default om ingen typ) | - |
| `partial` | Partiell plats (verifierad i testdata, ej i doc) | - |
| `pollingStation` | Röstningslokal | `canPrintDubblettrostkort: bool` |
| `mainPollingStation` | Vallokal | `canPrintDubblettrostkort: bool` |

Lista alla via `GET /placetype` (returnerar JSON-array av strängar).

## placeDetails - schema

```jsonc
{
  "info": "fritext om wifi/café/parkering m.m.",
  "hasToilet": false, "hasWifi": false, "hasCafe": false,
  "hasChargingStation": false, "hasParking": false,
  "accessibility": {
    "info": "fritext om tillgänglighet",
    "toiletAccessible": false, "toiletSoapNonAllergenic": false,
    "hasHearingLoop": false, "hasRamp": false
  }
}
```

## media - audio/video/images/links

Alla fyra arrayer har samma grundskelett:

```jsonc
{
  "media": {
    "audio": [{ "tags": ["audioguidning"], "url": "...", "providerRef": "...",
                "provider": "...", "title": "obligatoriskt", "description": "" }],
    "video": [{ /* samma + descriptionType */ }],
    "images": [{ /* samma + alternateDescription för alt-text */ }],
    "links": [{ "tags": [], "url": "...", "title": "...", "qr": "..." }]
  }
}
```

**Validering:** för audio/video/images måste antingen `url` finnas
**eller** `provider`+`providerRef` (eller båda).

## Curl-exempel

```bash
export APIKEY='din-svk-prod-nyckel'
BASE='https://api.svenskakyrkan.se/platser/v4'

# Sök plats på namn
curl -s "${BASE}/place?q=härnösands+domkyrka&apikey=${APIKEY}" | jq

# Hämta enskild plats (UUID, INTE slug)
curl -s "${BASE}/place/5dab016f-18f3-4973-92d8-69779653a1ef?apikey=${APIKEY}" | jq

# Bara öppettider
curl -s "${BASE}/place/5dab016f-18f3-4973-92d8-69779653a1ef?apikey=${APIKEY}" | jq '.openHours'

# Geosök inom 2 km från en koordinat (WGS84 lon,lat)
curl -s "${BASE}/place?nearby=17.939,62.633&nearbyRadius=2000&apikey=${APIKEY}" | jq

# Testdata (format {count, hits} istället för {totalHits, results})
curl -s "${BASE}/place?test=true&limit=3&apikey=${APIKEY}" | jq

# Lista alla platstyper
curl -s "${BASE}/placetype?apikey=${APIKEY}" | jq

# PATCH - uppdatera namn och öppettider på en plats
curl -s -X PATCH "${BASE}/place/<id>?apikey=${APIKEY}" \
  -H "Content-Type: application/json" \
  -d '{"updatedBy": "rasmus", "name": "Nytt namn", "openHours": null}'

# DELETE - logiskt borttagning (kräver deletedby)
curl -s -X DELETE "${BASE}/place/<id>?apikey=${APIKEY}&deletedby=rasmus"
```

## Intern admin-väg (CMS reverse-proxy)

Förutom den publika gatewayen finns ett **internt admin-API** på samma
domän som platsadministrationen (Content Studio):

- **Bas-URL:** `https://admin.svenskakyrkan.se/webapi/api-v2/place/{id}`
- **Auth:** sessionscookie `CS_UserSessionId` (124 tecken opaque,
  ASP.NET-session). Ingen API-nyckel.
- **Method:** `PUT` med **full replace** (hela Place-objektet, inte
  bara delta).
- **Header:** `Prefer: return=representation` ger uppdaterat objekt i
  svar (status 200).
- **Behörighet:** styrs av AD-grupper kopplade till SSO-användaren -
  cookien ger bara åtkomst till platser användaren äger.
- **CORS:** låst till `https://admin.svenskakyrkan.se` - browser
  cross-origin blockas, men server-till-server (vår dev-proxy)
  fungerar.
- **Timeout:** 90 minuter inaktivitet, ingen automatisk refresh.
  Ny cookie kräver ny SSO-inloggning i browser.

Detta är vägen som CMS:et själv använder för att spara öppettider när
du är inloggad. Det är **inte** en officiellt dokumenterad endpoint -
upptäcktes via reverse-engineering, se
[`docs-from-claude-code-chrome/platser-edit-flow-2026-05-01.md`](../../docs-from-claude-code-chrome/platser-edit-flow-2026-05-01.md).

`scripts/serve.py` i denna repo har en `/api/admin/`-proxy som lägger
till cookien från `CS_SESSION` i `.env` server-sidigt - se
[`platser-edit-app/`](../../platser-edit-app/).

## Skriv-operationer (PATCH/PUT/DELETE)

- **PATCH `/place/{id}`** - partiell uppdatering. Sätt fält till `null`
  för att rensa. **Listor ersätts som helhet** (ingen append).
- **PUT `/place`** - skapa ny plats. Returnerar 201 + Location-header.
- **PUT `/place/{id}`** - skriv över befintlig (alla fält ersätts).
- **DELETE `/place/{id}?deletedby=<user>`** - logisk borttagning. `deleted`
  och `deletedBy` sätts; `slug` ändras till `-deleted-` så namnet kan
  återanvändas. `deletedby`-param är obligatorisk (annars 400).
- **`?allowOverposting=true`** - tillåt skick av icke-ändringsbara fält
  (`id`, `slug`, `categories[].name` m.fl.) i payload utan att få
  validation-fel.
- **`?childAction=set-published,skip-depublished,disconnect`** - styr hur
  barnplatser hanteras vid uppdatering/borttagning av föräldraplats.

## Tvingande fält / specialregler

| Fält | Krav |
|---|---|
| `id` | Får aldrig anges i request - sätts av servern |
| `name` | Tvingande vid skapande, får aldrig sättas till null |
| `slug` | Får aldrig anges - beräknas av servern från owner+name |
| `created`, `updated`, `deleted` | Får aldrig anges - servern sätter |
| `createdBy`, `deletedBy`, `publishedBy`, `depublishedBy` | Får aldrig anges (men kan synas) |
| `updatedBy` | Tvingande vid skapa/uppdatera/ersätt, aldrig null |
| `published` | Får vara framåt/bakåt i tiden, eller null (utkast) |
| `depublished` | Får vara framåt/bakåt; om båda satta måste `depublished > published` |
| `owner.id`, `owner.type` | Tvingande vid skapande |
| `geolocation.geometry.coordinates` | Tvingande vid skapande |

## Föräldrar och barn

- En plats kan ha **en** förälder (`parent.id`).
- Förälder kan ha flera barn, men ingen relation i 3 nivåer.
- Barn returneras inte default vid sökning (måste be explicit).
- `?childAction=` styr beteende vid uppdatering/borttagning av förälder.

## Verifierat exempel - Härnösands domkyrka

```
id:    5dab016f-18f3-4973-92d8-69779653a1ef
slug:  20270-harnosands-domkyrkoforsamling-harnosands-domkyrka
owner: Härnösands domkyrkoförsamling (id 20270, Församling)
plats: Härnösand, Västernorrlands län (lkf 228001)
```

Öppettider per 2026-05-01 (en period från 2022-03-17, utan slutdatum):

| Dag | Öppet |
|---|---|
| Mån-Lör | 08:00 - 16:00 |
| Sön | 08:00 - 13:00 |

## Felkoder

| Kod | Betydelse |
|---|---|
| 200 | OK / hämtning lyckades |
| 201 | Created (PUT mot `/place`) - Location-header pekar på resursen |
| 204 | No Content (PATCH/DELETE lyckades) - Location-header för PATCH |
| 400 | Bad Request - body med textförklaring |
| 401 | Saknad / ogiltig API-nyckel |
| 403 | Saknad behörighet för operationen |
| 404 | Plats finns inte |
| 500 | Internt serverfel - body med textförklaring om möjligt |

## Användningsfall

- **Signage** - läs `openHours` för en plats och visa dagens öppettider.
- **Platser-edit-app** - PATCH för att uppdatera öppettider utan att gå
  via Content Studio (se `_todo.md`).
- Hitta närliggande kyrkor (`nearby` + `nearbyRadius`).
- Visa tillgänglighetsinfo (toalett, hörselslinga, ramp).
- Lista alla platser för en församling (`owner_id`).

## Begränsningar

- Många platser har tomma `openHours.periods: []` - öppettider är
  optionellt.
- Ingen explicit avvikelse-mekanism (t.ex. "stängt 24/12 eftermiddag")
  utöver fritextfältet `openHours.info`.
- Slug är inte permanent. Använd `id` (UUID) för referenser.
- Ordningen på koordinater är **lon, lat** enligt GeoJSON, INTE lat, lon.
