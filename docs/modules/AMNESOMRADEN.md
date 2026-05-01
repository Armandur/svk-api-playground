# Ämnesområden (Kategorier och Taggar v2)

Svenska kyrkans kategorier (delade mellan enheter) och taggar
(per enhet, namn unika per enhet). Används för att kategorisera och
"tagga" innehåll på flera plattformar.

## Snabbfakta

| Fält | Värde |
|---|---|
| Stil | OData v4 |
| Bas-URL prod | `https://api.svenskakyrkan.se/externwebb/api-v2/odata/` (samma instans som UnitAPI) |
| Bas-URL test | `https://api-t.svenskakyrkan.se/externwebb/api-v2/odata/` |
| Version | 2.0 |
| Auth | `HeaderApiKey` - `SvkAuthSvc-ApiKey: <key>` eller `?apikey=` |
| Verifierad | ✓ test 2026-05-01 (categories + tags) |
| Swagger UI | https://api.svenskakyrkan.se/externwebb/index.html?urls.primaryName=Kategorier%20och%20Taggar%20V2 |
| Swagger JSON | https://api.svenskakyrkan.se/externwebb/swagger/Kategorier%20och%20Taggarv2/swagger.json |
| Antal endpoints | 68 |

## Modell

Två huvudtyper av "ämnesområden":

- **Kategorier** - delas mellan alla enheter. Unikt namn globalt.
  Hierarkiska (parent/child). Kan kopplas till dokument.
- **Taggar** - per enhet (`unitId`). Namn unika *per enhet*.
  Hierarkiska (parent/child). Kan kopplas till dokument.

Båda har samma uppslagsmöjligheter: `{databaseId}`, `id={id}`,
`name='{name}'` (för taggar: `unitId={unitId}, name='{name}'`).

## Resurser - kategorier

```
GET /categories
GET /categories({databaseId})
GET /categories(id={id})
GET /categories(name='{name}')

# För varje uppslags-form finns relations-paths:
.../childCategories
.../childCategories({relatedDatabaseId})
.../childCategories(relatedId={relatedId})
.../childCategories(relatedName='{relatedName}')
.../parentCategory
.../parentCategory/$ref
.../documents
.../documents({relatedDocumentId})
.../documents(relatedGuoid='{relatedGuoid}')
.../documents(relatedVirtualUrl='{relatedVirtualUrl}')
```

## Resurser - taggar

```
GET /tags
GET /tags({databaseId})
GET /tags(id={id})
GET /tags(unitId={unitId}, name='{name}')

# Samma relations-paths som kategorier:
.../childTags
.../parentTag
.../documents
```

Special för childTags: `relatedUnitId` ingår eftersom barntaggar är per
enhet:
`childTags(relatedUnitId={relatedUnitId}, relatedName='{relatedName}')`.

## Verifierad fältuppsättning (categories)

Anrop `GET /categories?$top=3` mot test 2026-05-01 returnerade fälten:

```
databaseId, id (UUID), parentId, name, description, modifiedDate,
showCategory, parentDatabaseId
```

Exempel: `databaseId=215, name="0-18"`, `databaseId=216, name="Agera"`.

## Curl-exempel

```bash
export APIKEY='din-svk-api-nyckel'
# Använd test-bas tills nyckeln är godkänd för prod
BASE='https://api-t.svenskakyrkan.se/externwebb/api-v2/odata'

# Lista kategorier
curl -s "${BASE}/categories?\$top=10" \
  -H "SvkAuthSvc-ApiKey: ${APIKEY}" | jq

# Slå upp kategori på namn
curl -s "${BASE}/categories(name='Gudstjänst')" \
  -H "SvkAuthSvc-ApiKey: ${APIKEY}" | jq

# Barn-kategorier
curl -s "${BASE}/categories(name='Gudstjänst')/childCategories" \
  -H "SvkAuthSvc-ApiKey: ${APIKEY}" | jq

# Dokument taggade med kategorin
curl -s "${BASE}/categories(name='Gudstjänst')/documents?\$top=5" \
  -H "SvkAuthSvc-ApiKey: ${APIKEY}" | jq

# Slå upp tagg på enhet + namn
curl -s "${BASE}/tags(unitId=1996,name='advent')" \
  -H "SvkAuthSvc-ApiKey: ${APIKEY}" | jq

# Lista alla taggar för en enhet (via filter)
curl -s "${BASE}/tags?\$filter=unitId eq 1996" \
  -H "SvkAuthSvc-ApiKey: ${APIKEY}" | jq
```

## Användningsfall

- Hämta navigations-trädet av kategorier för en webbsida.
- Visa alla artiklar under en kategori.
- Tagg-cloud för en enhet.
- Föreslå relevanta taggar baserat på existerande hierarki.

## Relationer

- **Documents** - kategorier och taggar refererar till dokument via
  `relatedGuoid`/`relatedVirtualUrl`/`relatedDocumentId` (samma
  identifierare som [UnitAPI](#UNITAPI):s websites).
- **UnitAPI** - taggar är skopade per `unitId`.

## Hämta full Swagger lokalt

```bash
curl -s 'https://api.svenskakyrkan.se/externwebb/swagger/Kategorier%20och%20Taggarv2/swagger.json' \
  -o tmp/swagger_amnesomraden.json
jq '.paths | keys | length' tmp/swagger_amnesomraden.json    # => 68
```
