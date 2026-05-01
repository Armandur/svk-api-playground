# Församlingskartor

GIS-lager med Svenska kyrkans indelning - stift, kontrakt, ekonomiska
enheter (pastorat och församlingar med egen ekonomi) och församlingar.
Historiska lager från 2008 och framåt; i viss mån även framtida
indelning när den är beslutad.

## Snabbfakta

| Fält | Värde |
|---|---|
| Protokoll | OGC WMS (bilder) + WFS (vektordata till QGIS) |
| WMS bas-URL | `https://flax.svenskakyrkan.se/geoserver/uff/wms` |
| WFS bas-URL | `https://flax.svenskakyrkan.se/geoserver/uff/wfs` (analogt) |
| Koordinatsystem | SWEREF 99 TM (EPSG:3006) |
| Auth | Saknas (öppet) - WMS/WFS-standarder förlitar sig på operatörens egen access-modell |
| Doc | https://api.svenskakyrkan.se/doc/forsamlingskarta/forsamlingskarta_doc.aspx |

## Lagernamn

```
uff:stift_<datum>
uff:kontrakt_<datum>
uff:ekonomiska_enheter_<datum>
uff:forsamlingar_<datum>
```

`<datum>` är ikraftträdandedatum för indelningen, t.ex.
`uff:forsamlingar_2012-01-01`. Vill man se nuvarande indelning - använd
det senaste datumet som `GetCapabilities` listar.

## Curl-exempel

```bash
# Lista alla tillgängliga lager
curl -s 'https://flax.svenskakyrkan.se/geoserver/uff/wms?service=wms&version=1.3.0&request=GetCapabilities' | xmllint --format - | head -120

# Hämta en PNG av församlingar 2012-01-01 över hela Sverige
curl -s 'https://flax.svenskakyrkan.se/geoserver/ows?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&BBOX=6111275,245118,7670000,910000&CRS=EPSG:3006&WIDTH=800&HEIGHT=1200&LAYERS=uff:forsamlingar_2012-01-01&FORMAT=image/png' \
  -o forsamlingar_2012.png

# WFS GetCapabilities
curl -s 'https://flax.svenskakyrkan.se/geoserver/uff/wfs?service=wfs&version=2.0.0&request=GetCapabilities' | head -120

# Hämta en specifik församling som GeoJSON
curl -s 'https://flax.svenskakyrkan.se/geoserver/uff/wfs?service=wfs&version=2.0.0&request=GetFeature&typeNames=uff:forsamlingar_2012-01-01&CQL_FILTER=namn=%27Bollnäs%20församling%27&outputFormat=application/json' | jq
```

## Användning i QGIS

Svenska kyrkan tillhandahåller **inte** bakgrundskarta. För att lägga
till en sverigekarta i QGIS:

- Använd OpenLayers Plugin (extrahera till
  `[QGIS-installation]\apps\qgis-ltr\python\plugins\`).
- Sedan: meny `Web > OpenLayersPlugin > <bakgrund>` (Bing Aerial m.fl.).
- Lägg till SVK-lagren via WMS- eller WFS-anslutning till URL:erna ovan.

Kompatibilitet: doc:en nämner att QGIS 2.8 eller tidigare kan behövas;
nyare versioner kan kräva justering.

## Användningsfall

- Visa församlingsgränser i en kart-applikation.
- GIS-analyser (vilka adresser tillhör vilken församling).
- Historiska jämförelser av indelning.

## Begränsningar

- Bara svenskt land - inga utlandsförsamlingar.
- WMS/WFS - inte ett REST-API. Klienter behöver kunna OGC-protokollen.
- Renderingen måste lösas själv (utöver det som GeoServer ger via WMS).
