# UnitAPI (Enheter v2)

OData-API för sökning av enheter och projekt kopplade till webbsidor
och kalenderhändelser. Centralt id-system för Svenska kyrkans organisation.

## Snabbfakta

| Fält | Värde |
|---|---|
| Stil | OData v4 |
| Bas-URL prod | `https://api.svenskakyrkan.se/externwebb/api-v2/odata/` |
| Bas-URL test | `https://api-t.svenskakyrkan.se/externwebb/api-v2/odata/` |
| Version | 2.0 |
| Auth | `HeaderApiKey` - `SvkAuthSvc-ApiKey: <key>` eller `?apikey=` |
| Verifierad | ✓ test 2026-05-01 (samma OData-produkt täcker även Ämnesområden) |
| Swagger UI | https://api.svenskakyrkan.se/externwebb/index.html?urls.primaryName=Enheter%20V2 |
| Swagger JSON | https://api.svenskakyrkan.se/externwebb/swagger/Enheterv2/swagger.json |
| Antal endpoints | 14 |

## Endpoints

```
GET /units                                                       (lista)
GET /units({unitId})                                             (enskild)
GET /units({unitId})/childUnits
GET /units({unitId})/childUnits({relatedUnitId})
GET /units({unitId})/parentUnit
GET /units({unitId})/parentUnit/$ref
GET /units({unitId})/eventUnitInfos
GET /units({unitId})/eventUnitInfos({relatedDocumentId}, {relatedUnitId})
GET /units({unitId})/websites
GET /units({unitId})/websites({relatedDocumentId})
GET /units({unitId})/websites(relatedGuoid='{relatedGuoid}')
GET /units({unitId})/websites(relatedWebId={relatedWebId})
GET /units({unitId})/websites(relatedVirtualUrl='{relatedVirtualUrl}')
GET /units/collective(unitId={id}, includeParentsAndSiblings={bool}, noFilter={bool})
```

`{unitId}` är heltal (matchar `enhetsid` från Församlingssök/Enhetsinformation).
Single quotes runt strängvärden (`'foo'`), ej runt heltal/booleans -
OData-syntax.

## Datamodell - `Unit`

Från `swagger.json` (lokal kopia: `tmp/swagger_enheter.json`):

| Fält | Typ | Anteckning |
|---|---|---|
| `unitId` | integer | Primärnyckel, samma som `enhetsid` i andra API:er |
| `name` | string | T.ex. "Uppsala stift" |
| `extranetWebId` | integer | Id för externwebbsida |
| `intranetWebId` | integer | Id för intranätssida |
| `validUntil` | string (date) | Utgångsdatum (för avvecklade enheter) |
| `activeFrom` | string (date) | Startdatum |
| `unitType` | enum | Se nedan |
| `stiftCode` | string | 2-siffrig stiftkod, t.ex. `02` (Uppsala) |
| `samfCode` | string | Samfällighetskod, 6 siffror, t.ex. `020116` |
| `visitingAddress1`, `visitingAddress2` | string | Besöksadress rad 1/2 |
| `visitingPostAddress` | string | Postnr + ort för besök |
| `visitingPostCOAddress` | string | C/O-adress för besök |
| `country`, `postCountry` | string | Land för besök/post |
| `corporateIdentityNumber` | string | Organisationsnummer (10 siffror) |
| `postAddress1`, `postAddress2` | string | Postadress |
| `postPostAddress` | string | Postnr + ort för post |
| `phoneNumber` | string | Telefon |
| `emailAddress` | string | E-post (i schemat - kan saknas i svar) |
| `websiteAddress` | string | URL till hemsida |
| `skp` | string | Svenska kyrkans interna kod |
| `lkf` | string | Län-kommun-församling-kod (SCB) |
| `contract` | string | Kontraktskod, 4 siffror, t.ex. `0201` |
| `localAuthorityCode` | string | Kommunkod |
| `activatedCalendar` | boolean | Har kalendertjänst aktiverad |
| `calendarUrl` | string | URL till enhetens kalender |
| `parentUnitId` | integer | Förälder (stift > pastorat > församling) |

### `unitType` - enum

`Ingen`, `Församling`, `FörsamlingE` (egen ekonomi), `Sammfällighet`,
`Utlandet`, `Stift`, `Projekt`.

#### Volymsiffror prod 2026-05-05 (totalt 2 220 enheter)

| `unitType` | Antal | Anteckning |
|---|---|---|
| `Församling` | 908 | Församlingar utan egen ekonomi - tillhör pastorat |
| `Projekt` | 677 | |
| `FörsamlingE` | 354 | Församling med egen ekonomi (jure egen) |
| `Sammfällighet` | 229 | Pastorat (felstavat - se ovan) |
| `Utlandet` | 37 | |
| `Stift` | 13 | `parentUnitId: null` - toppen av hierarkin |
| `Ingen` | 2 | Kyrkokansliet m.fl. |

"Ekonomiska enheter" (de som har egen ekonomi och egen budget) =
`Stift` + `Sammfällighet` + `FörsamlingE` = 596 st.

### `stiftCode` - mappning till stiftnamn

`stiftCode` finns på alla typer av enheter (förutom `Projekt`). För att
mappa till stiftnamn: hämta alla `Stift`-enheter och bygg en lookup
`stiftCode -> name`. Stiften har sin egen kod i `stiftCode`.

| `stiftCode` | Stift |
|---|---|
| `01` | Uppsala stift |
| `02` | Linköpings stift |
| `03` | Skara stift |
| `04` | Strängnäs stift |
| `05` | Västerås stift |
| `06` | Växjö stift |
| `07` | Lunds stift |
| `08` | Göteborgs stift |
| `09` | Karlstads stift |
| `10` | Härnösands stift |
| `11` | Luleå stift |
| `12` | Visby stift |
| `13` | Stockholms stift |

> **Stavfel:** `Sammfällighet` (två m) är felstavat - korrekt svenska
> är "Samfällighet" med ett m. Felet är genomgående i SVK:s API och
> värde-baserat (inte bara label) så ev. rättning kräver både kodfix
> och datamigration. Klienter måste matcha den felaktiga formen
> tills SVK åtgärdat det. UI-strängar kan mappa till "Pastorat" vid
> presentation eftersom det är vad enhetstypen vanligen kallas i
> kyrkans dagliga språk.

### Verifierat exempel (test 2026-05-01)

- `unitId=1` = "Kyrkokansliet - Ägarweb" (unitType: Ingen)
- `unitId=2` = "Uppsala stift" (unitType: Stift, stiftCode: 02,
  corporateIdentityNumber: 7700010000)
- `unitId=3` = "Linköpings stift", `unitId=4` = "Skara stift",
  `unitId=5` = "Strängnäs stift" (alla med `parentUnitId: null` -
  stiften är toppen).

## Andra exponerade modeller

Swagger-dokumentationen exponerar följande relaterade modeller (utöver
`Unit`):

`Website`, `EventUnitInfo`, `PlaceInfo`, `PlaceItem`, `Document`,
`DocumentComment`, `DocumentIndex`, `DocumentRelation`,
`DocumentStatistic`, `Image`, `ImageCollection`, `ImageInfo`,
`StandardPage`, `Tag`, `Category`, `Subscription`, `User`,
`UserProfile`, `Group`, `Attention`, m.fl.

Notera att de exponeras som tillgängliga via OData-relationer från
`/units(id)/...` (t.ex. `websites`, `eventUnitInfos`).

## Curl-exempel

```bash
export APIKEY='din-svk-api-nyckel'
# Använd test-bas tills nyckeln är godkänd för prod
BASE='https://api-t.svenskakyrkan.se/externwebb/api-v2/odata'

# Lista första 10 enheter
curl -s "${BASE}/units?\$top=10" \
  -H "SvkAuthSvc-ApiKey: ${APIKEY}" | jq

# Enskild enhet
curl -s "${BASE}/units(1996)" \
  -H "SvkAuthSvc-ApiKey: ${APIKEY}" | jq

# Barn-enheter (t.ex. församlingar under ett pastorat)
curl -s "${BASE}/units(1996)/childUnits" \
  -H "SvkAuthSvc-ApiKey: ${APIKEY}" | jq

# Föräldra-enhet
curl -s "${BASE}/units(1996)/parentUnit" \
  -H "SvkAuthSvc-ApiKey: ${APIKEY}" | jq

# Webbsidor kopplade till enheten
curl -s "${BASE}/units(1996)/websites" \
  -H "SvkAuthSvc-ApiKey: ${APIKEY}" | jq

# Slå upp enhet via webbsidans virtual URL
curl -s "${BASE}/units(1996)/websites(relatedVirtualUrl='/forsamling-x')" \
  -H "SvkAuthSvc-ApiKey: ${APIKEY}" | jq

# Collective-funktion: enhet + alla föräldrar och syskon
curl -s "${BASE}/units/collective(unitId=1996, includeParentsAndSiblings=true, noFilter=false)" \
  -H "SvkAuthSvc-ApiKey: ${APIKEY}" | jq
```

## OData-filtrering och projektion

Standard OData v4 query-options fungerar:

```bash
# Top + skip = paging
curl -s "${BASE}/units?\$top=20&\$skip=40" -H "SvkAuthSvc-ApiKey: ${APIKEY}"

# Filter (om fältet är filtrerbart)
curl -s "${BASE}/units?\$filter=name eq 'Bollnäs församling'" -H "SvkAuthSvc-ApiKey: ${APIKEY}"

# Välj specifika fält
curl -s "${BASE}/units?\$select=id,name,type" -H "SvkAuthSvc-ApiKey: ${APIKEY}"

# Expandera relaterade
curl -s "${BASE}/units(1996)?\$expand=childUnits" -H "SvkAuthSvc-ApiKey: ${APIKEY}"

# Räkna
curl -s "${BASE}/units?\$count=true&\$top=0" -H "SvkAuthSvc-ApiKey: ${APIKEY}"
```

`$` måste escapas i shell (`\$`) eller skickas i query-string utan escape.

### Begränsningar och fallgropar

- **Max `$top` = 1000.** Större värden ger HTTP 400
  (`The limit of '1000' for Top query has been exceeded`). Paginera med
  `$skip` för att hämta hela datasetet.
- **`$filter` på `unitType` med åäö är trasigt på serversidan.** Filter
  som `$filter=unitType eq 'FörsamlingE'` ger HTTP 400 med
  `The string 'FÃ¶rsamlingE' is not a valid enumeration type constant`
  oavsett hur klienten encodar URL:en - servern dekodar UTF-8 som
  Latin-1. Workaround: hämta alla enheter (2 220 st) och filtrera
  klientside.
- **`emailAddress` finns sällan** i svar trots att det finns i schemat.
- **Pilot-projekt i detta repo** kan använda `scripts/serve.py`-proxyn
  (`/api/units/...`) för att slippa hantera nyckeln klientside - se
  `SVK_PROXY_ROUTES` i `serve.py`.

## Användningsfall

- Hämta hierarki: stift -> kontrakt -> pastorat -> församling.
- Mappa en webbsidas URL till organisatorisk enhet.
- Lista alla webbsidor kopplade till en enhet.
- Bygg sidofält "om denna församling" baserat på `units/collective(...)`.

## Relationer till andra API:er

- **Församlingssök** ger `enhetsid` som passar in i `{unitId}`.
- **Enhetsinformation** har överlappande data men annan strukturering.
- **CalendarAPI** refererar till `unitId` för ägande enhet av events.
- **Ämnesområden** (`tags`) använder `unitId` för att skopa taggar per enhet.

## Hämta full Swagger lokalt

```bash
curl -s 'https://api.svenskakyrkan.se/externwebb/swagger/Enheterv2/swagger.json' -o tmp/swagger_unitapi.json
jq '.paths | keys' tmp/swagger_unitapi.json
```
