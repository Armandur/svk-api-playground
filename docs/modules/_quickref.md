# Quickref - copy-paste-bara curl-exempel

Sätt nyckeln en gång:

```bash
export APIKEY='din-svk-api-nyckel'
export AZURE_KEY='din-azure-apim-subscription-key'   # behövs bara för CalendarAPI
```

## Bönewebben - tända ljus och böner

```bash
# Metadata för allhelgona-eventet (totalt antal ljus + böner)
curl -s "https://be.svenskakyrkan.se/api/event/allhelgona/" | jq '.data.metadata, .data.candles.count, .data.prayers.count'

# Senaste 20 ljusen med text
curl -s "https://be.svenskakyrkan.se/api/event/allhelgona/candles-with-text/20/0/" | jq '.data.thoughts[] | {created, text}'

# Geo-positioner i tag allhelgona2025 (paginera 1000 åt gången)
curl -s "https://be.svenskakyrkan.se/api/geo-positions/tags/allhelgona2025/candles/1000/0/" | jq '.data.metadata'

# Topp 5 kyrkor med flest ljus
curl -s "https://be.svenskakyrkan.se/api/geo-positions/tags/allhelgona2025/candles/1000/0/" \
  | jq '.data.rooms.results | sort_by(-.count) | .[0:5]'
```

## CalendarAPI - sök events

```bash
# Bas-URL är Azure-gateway, INTE api.svenskakyrkan.se
curl -s "https://svk-apim-prod.azure-api.net/calendar/v1/event/search?q=gudstjänst&limit=5" \
  -H "Ocp-Apim-Subscription-Key: ${AZURE_KEY}" | jq

# Tidsbaserad sökning (publika events i maj)
curl -s "https://svk-apim-prod.azure-api.net/calendar/v1/event/search?from=2026-05-01&to=2026-05-31&access=External&limit=20" \
  -H "Ocp-Apim-Subscription-Key: ${AZURE_KEY}" | jq '.result[] | {title, start, end}'
```

## Kyrkoåret + bibeltexter - hela året

```bash
# Innevarande kyrkoår (default)
curl -s "https://www.svenskakyrkan.se/webapi/api-v2/churchcalendar?apiKey=139ff33b-4451-4f0f-b397-1f4ec9307a87" | jq '.[0]'

# Specifikt år (mappar mot kalenderåret för 1:a advent som startade kyrkoåret)
curl -s "https://www.svenskakyrkan.se/webapi/api-v2/churchcalendar/2025?apiKey=139ff33b-4451-4f0f-b397-1f4ec9307a87" | jq 'length'
```

## Enhetsinformation - en enhet

```bash
# Doc-sidan visar exakta paths
open https://api.svenskakyrkan.se/enhetsinfo/v2/doc/
```

## Församlingskartor - WMS GetCapabilities

```bash
curl -s 'https://flax.svenskakyrkan.se/geoserver/uff/wms?service=wms&version=1.3.0&request=GetCapabilities' | head -c 2000
```

## Församlingssök - vilken församling tillhör adressen?

```bash
# Via adressplatsid (UUID, snabbast)
curl -s "https://flax.svenskakyrkan.se/flax/api/forsamlingsid?adressplatsid=21837641-e46d-40e2-8c83-5cca373deab0" \
  -H "SvkAuthSvc-ApiKey: ${APIKEY}"

# Via fri text-adress
curl -s -G "https://flax.svenskakyrkan.se/flax/api/forsamlingsid" \
  --data-urlencode "adress=Polacksgatan 10 C" \
  --data-urlencode "postnr=821 33" \
  --data-urlencode "postort=Bollnäs" \
  -H "SvkAuthSvc-ApiKey: ${APIKEY}"

# Via SWEREF 99 TM-koordinater
curl -s "https://flax.svenskakyrkan.se/flax/api/forsamlingsid?n=6800224&e=574676" \
  -H "SvkAuthSvc-ApiKey: ${APIKEY}"
```

## KBR - Linköpings domkyrka med alla fält

```bash
curl -s "https://api.svenskakyrkan.se/kbr/api/byggnad/32555?fields=*&apikey=${APIKEY}" | jq

# 20 första kyrkorna
curl -s "https://api.svenskakyrkan.se/kbr/api/byggnader?kyrka=true&limit=20&fields=namn,id,pastorat,stift&apikey=${APIKEY}" | jq

# Sök på namn (innehåller)
curl -s "https://api.svenskakyrkan.se/kbr/api/byggnader?namn=~mora&apikey=${APIKEY}" | jq

# Ändrade efter datum
curl -s "https://api.svenskakyrkan.se/kbr/api/byggnader?andraddatum=20240101-&apikey=${APIKEY}" | jq
```

## K-samsök (RAÄ) - öppet, korslänka från KBR

```bash
# Hämta ett BBR-objekt direkt via persistent URI (JSON-LD)
curl -s -H "Accept: application/json" \
  "https://kulturarvsdata.se/raa/bbr/21400000148207" | jq '.["@graph"][0]'

# Fritextsökning
curl -s 'https://kulturarvsdata.se/ksamsok/api?method=search&version=1.1&hitsPerPage=5&query=text=runsten'

# Alla bilder kopplade till en byggnad (foton ligger på pub.raa.se)
curl -s 'https://kulturarvsdata.se/ksamsok/api?method=getRelations&version=1.1&relation=isVisualizedBy&objectId=raa/bbr/21400000148207'

# Korslänka: KBR-id 32494 -> BBR -> K-samsök
BBR=$(curl -s "https://api.svenskakyrkan.se/kbr/api/byggnad/32494?fields=identitetRAA&apikey=${APIKEY}" | jq -r '.identitetRAA')
curl -s -H "Accept: application/json" "https://kulturarvsdata.se/raa/bbr/${BBR}" | jq '.["@graph"][0]["ns5:itemLabel"]'
```

## Platser - hämta plats

```bash
curl -s "https://api.svenskakyrkan.se/platser/v4/place?apikey=${APIKEY}" | jq
```

## UnitAPI - lista enheter, sök webbsida

```bash
# Lista enheter
curl -s "https://api.svenskakyrkan.se/externwebb/api-v2/odata/units?\$top=10" \
  -H "SvkAuthSvc-ApiKey: ${APIKEY}" | jq

# Slå upp på virtual URL
curl -s "https://api.svenskakyrkan.se/externwebb/api-v2/odata/units(1)/websites(relatedVirtualUrl='/forsamling-x')" \
  -H "SvkAuthSvc-ApiKey: ${APIKEY}" | jq
```

## Ämnesområden - kategorier och taggar

```bash
# Lista kategorier
curl -s "https://api.svenskakyrkan.se/externwebb/api-v2/odata/categories?\$top=10" \
  -H "SvkAuthSvc-ApiKey: ${APIKEY}" | jq

# Slå upp kategori på namn
curl -s "https://api.svenskakyrkan.se/externwebb/api-v2/odata/categories(name='Gudstjänst')" \
  -H "SvkAuthSvc-ApiKey: ${APIKEY}" | jq

# Taggar för en enhet på namn
curl -s "https://api.svenskakyrkan.se/externwebb/api-v2/odata/tags(unitId=1,name='advent')" \
  -H "SvkAuthSvc-ApiKey: ${APIKEY}" | jq
```

## Snabb introspektion - vilka publika produkter finns på Azure?

```bash
BASE='https://svk-apim-prod.management.azure-api.net/subscriptions/000/resourceGroups/000/providers/Microsoft.ApiManagement/service/svk-apim-prod'
curl -s "${BASE}/products?api-version=2022-04-01-preview" | jq '.value[] | {name, displayName: .properties.displayName, state: .properties.state}'
```
