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
| `owner_id=<id>` eller `owner_id=<id1>,<id2>,...` | Filter på ägare ("is any of" - kommaseparerat) |
| `owner_type=Församling\|Sammfällighet\|Stift\|...` | Filter på enhetstyp. Servern använder `Sammfällighet` för det som UI:t kallar "Pastorat" |
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

## openHours - validering

Servern (både publika gatewayen och admin-proxyn) validerar:

- **`validFrom < validTo` strikt** - servern tillåter inte
  `validFrom == validTo`. Lägsta period-längd är 2 dygn (en dag +
  dagen efter). Verifierat 2026-05-01: PUT med `validFrom=2025-05-01,
  validTo=2025-05-01` → HTTP 400 *"The date in validFrom must be a
  date before validTo"*.
- **Intervall får inte överlappa inom samma dag** - PUT med t.ex.
  `mo: [{from:"09:00",to:"17:00"},{from:"10:00",to:"12:00"}]` → HTTP
  400 *"Times cannot overlap. From: 10:00 To: 12:00, From: 09:00,
  To: 17:00"*.
- **Tomma dayKey-arrays strippas** vid PUT/PATCH. Om du skickar
  `days: {mo: [], tu: [...]}` så returneras vid nästa GET bara
  `days: {tu: [...]}` - `mo` är borta. Funktionellt samma resultat
  (saknad nyckel = stängt) men klienter kan inte lita på att tomma
  arrays finns kvar efter en sparning.

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

### `openHours.info` - generell fritextruta

Inte dokumenterad i den publika `/doc/api/index` men finns i live-
data och accepteras av admin-flödets PUT. **En enda generell
fritextruta** för hela platsen - det finns inget per-dag- eller
per-period-kommentarsfält i schemat.

Vår `platser-edit-app/` skriver datum-prefixade rader när man
"Stänger en specifik dag" (`Stängt fredag 1 maj 2026: julafton`)
och appendar till `info`-fältet. `signage-platser/`-vyn renderar
fältet med `white-space: pre-line` så `\n`-tecken bryter rader
visuellt.

**Caveat:** att skicka `info: null` eller `info: ""` tolkas av
admin-servern som "ta bort fältet". Klienter som inte aktivt
vill rensa info ska utelämna fältet från payloaden helt.

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
domän som platsadministrationen (Content Studio). Det är vägen som
CMS:et själv använder. **Inte** officiellt dokumenterad - upptäcktes
via reverse-engineering, se
[`docs-from-claude-code-chrome/platser-edit-flow-2026-05-01.md`](../../docs-from-claude-code-chrome/platser-edit-flow-2026-05-01.md).
End-to-end-verifierad mot Härnösands domkyrka 2026-05-01.

### Endpoints

| Path | Method | Beskrivning |
|---|---|---|
| `https://admin.svenskakyrkan.se/webapi/api-v2/place/{id}` | GET | Hämta plats |
| `https://admin.svenskakyrkan.se/webapi/api-v2/place/{id}` | PUT | **Full replace** - hela Place-objektet, inte delta |
| `https://admin.svenskakyrkan.se/webapi/api-v2/place/{id}` | PATCH/DELETE | Antas finnas men inte testat |
| `https://admin.svenskakyrkan.se/webapi/api-v3/...` | GET (SSE) | Realtids-events via `Content-Type: text/event-stream` (api-v**3**, inte v2) |
| `https://admin.svenskakyrkan.se/churchcontext` | GET | Returnerar inloggad users config + AD-grupper. Se nedan. |
| `https://admin.svenskakyrkan.se/webapi/api-v2/Account/Login` | GET | SAML/WS-Federation-redirect (returneras vid 401) |

### `/churchcontext` - användarens kontext

Endpointen returnerar **inte** JSON utan en JS-fil:

```javascript
var churchContext={"isIntranet":false,"isProduction":false,"user":{...},...};
function() { ... self.adminWebName = '...'; ... }
```

Klienter måste extrahera den första balanserade `{...}` efter `var
churchContext=` (vår dev-proxy gör detta automatiskt på
`/api/admin/_churchcontext`).

Centralt fält: **`user.groups`** är en lista av AD-grupp-namn med
formatet:

```
Ext\740_<unitId>_Externwebbsredaktör <namn>
```

Exempel:

```
Ext\740_2022_Externwebbsredaktör Häggdångers församling
Ext\740_20271_Externwebbsredaktör Härnösands pastorat
```

Mönstret `^Ext\\740_(\d+)_` extraherar enhets-id:n (`unitId`) som matchar
`owner.id` på platser. Genom att filtrera Platser-API på
`?owner_id=<id1>,<id2>,...` får man bara platser användaren har
skrivbehörighet på - vilket är hur `platser-edit-app/`s "Mina platser"-
flöde fungerar.

Andra grupper i `user.groups` har andra prefix (`KAP\redaktör_*`,
`BUILTIN\Users`, `CS-BUILTIN\External users` m.fl.) som vi inte
parsar idag.

### Auth - cookie-baserad

Inga API-nycklar. Auth är **cookie-baserad** med flera samverkande
cookies. Alla måste skickas i `Cookie:`-header för att flödet ska
fungera:

| Cookie | Längd | HttpOnly | Roll |
|---|---|---|---|
| `.Prod2.AuthCookie` | varierar | ✓ | **Kritisk auth-cookie**. ASP.NET Core auth-ticket. Utan den → 401 + redirect till /Account/Login |
| `ASP.NET_SessionId` | ~24 tecken | ✓ | Klassisk ASP.NET-sessionscookie |
| `CS_UserSessionId` | 124 tecken | nej | Applikations-session (komplement, räcker inte själv) |
| `TS0174741b` | 202 tecken | nej | F5 BIG-IP / TrafficShield WAF-cookie. **Roteras vid varje anrop** (anti-replay) |
| `AdminWebId` | 6 siffror | nej | Användar-ID |

`ai_user` och `ai_session` (Azure Application Insights) behöver inte
skickas - tracking only.

### Headers vid skrivande operationer

```
Cookie: .Prod2.AuthCookie=...; ASP.NET_SessionId=...; CS_UserSessionId=...; TS0174741b=...; AdminWebId=...
Origin: https://admin.svenskakyrkan.se
Referer: https://admin.svenskakyrkan.se/
X-Requested-With: XMLHttpRequest
Content-Type: application/json
Prefer: return=representation
```

`X-Requested-With` är viktig - utan den avvisar ASP.NET ofta requests
med generisk 401 även om cookies är giltiga.

### Sessionsbeteende

- **Timeout:** 90 minuter **inaktivitet** (sliding). Aktivitet förlänger
  timern.
- **Sliding expiration utan rotation:** `.Prod2.AuthCookie`,
  `ASP.NET_SessionId`, `CS_UserSessionId` har samma värde under hela
  sessionens livslängd. Servern förlänger giltighet *internt* utan att
  utfärda nya `Set-Cookie`-headers.
- **WAF-rotation:** `TS0174741b` roteras vid **varje anrop** (verifierat
  i dev.log) och måste skickas tillbaka i nästa anrop. F5 BIG-IP
  anti-replay-skydd. Klient som inte uppdaterar TS-token kan börja
  få avvisade requests.
- **Ingen programmatisk refresh:** ny cookie kräver ny SSO-inloggning
  via browser. `/Account/Login` redirectar till SAML/WS-Federation-IdP
  (ADFS/Azure AD) och kräver browser-interaktion.

### CORS

`Access-Control-Allow-Origin: https://admin.svenskakyrkan.se` +
`Vary: Origin`. Browser-clients på andra origins blockeras. **Server-
till-server** (t.ex. vår dev-proxy) bryr sig inte om CORS och kan
göra anrop fritt - så länge cookies + Origin/Referer-headers skickas.

### Behörighet

Styrs av AD-gruppmedlemskap som bestäms vid SSO-inloggning. Cookien
ger bara skriv-access till platser där användaren är medlem av rätt
KAP-/Ext-grupp. PUT mot en plats utanför scope ger 403.

### Implementation i denna repo

`scripts/serve.py` har en `/api/admin/`-proxy:

- Tar cookie-header från env-var `CS_SESSION` eller via runtime-endpoint
  `POST /api/admin/_session`.
- Stödjer GET, PATCH, PUT, DELETE - server-till-server, kringgår CORS.
- Sniffar `Set-Cookie` i upstream-svar via `apply_set_cookies()` och
  uppdaterar lagrad cookie-header (täcker TS-rotation).
- Bakgrundstråd `keep_session_alive()` pingar `/churchcontext` var
  30:e minut (konfigurerbart via `ADMIN_KEEPALIVE_MIN`) för att hålla
  sliding-timern levande.
- Diagnostik-endpoint `GET /api/admin/_session` exponerar `set`,
  `length`, `preview`, `last_pinged_at`, `last_ping_status`,
  `last_rotated_at`.

`platser-edit-app/` bygger på proxyn med ett UI för att klistra in
cookies från DevTools (HttpOnly cookies syns inte via JS), pinga
manuellt och redigera öppettider via PUT.

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
