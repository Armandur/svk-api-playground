# Församlingskartor

GIS-lager med Svenska kyrkans indelning - stift, kontrakt, ekonomiska
enheter (pastorat och församlingar med egen ekonomi) och församlingar.
Historiska lager från 2008 och framåt; i viss mån även framtida
indelning när den är beslutad.

## Snabbfakta

| Fält | Värde |
|---|---|
| Protokoll | OGC WMS (bilder) + WFS (vektordata till QGIS) **eller** direkthämtning som zip-shapefile |
| WMS bas-URL | `https://flax.svenskakyrkan.se/geoserver/uff/wms` |
| WFS bas-URL | `https://flax.svenskakyrkan.se/geoserver/uff/wfs` (analogt) |
| Zip bas-URL | `https://api.svenskakyrkan.se/kartor/{layer}_{year}-01-01.zip` |
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

## Direkthämtning som zip

Förutom WMS/WFS finns shapefile-zip:ar för direkt-nedladdning på
`api.svenskakyrkan.se/kartor/`. Bekvämt för batch-jobb och offline-bygge:

```bash
curl -O 'https://api.svenskakyrkan.se/kartor/forsamlingar_2026-01-01.zip'
curl -O 'https://api.svenskakyrkan.se/kartor/ekonomiska_enheter_2026-01-01.zip'
```

| Lager | Storlek 2026 | Antal features 2026 |
|---|---|---|
| `stift` | ~? | 13 |
| `kontrakt` | ~? | 96 |
| `ekonomiska_enheter` | ~7 MB | 568 |
| `forsamlingar` | ~12 MB | 1251 |

**Verifierade årgångar**: 2008-2026 finns alla för `forsamlingar` och
`ekonomiska_enheter` (testade med HEAD-request 2026-05).

### Zip-strukturer (gotchas)

Filerna inuti zip:en ligger på olika ställen beroende på årgång:

- **2008-2024**: filerna ligger på zip-roten (`forsamlingar_2014-01-01.shp`)
- **2026**: filerna ligger i en mapp (`forsamlingar_2026-01-01/forsamlingar_2026-01-01.shp`)

Hantera båda i öppningskoden:

```python
stem = f"{layer}_{year}-01-01"
candidates = [stem, f"{stem}/{stem}"]
base = next((c for c in candidates if f"{c}.shp" in zf.namelist()), None)
```

### Property-fält per lager

Varje lager har sitt eget identifierar-fält:

| Lager | Kod-fält | Namnfält |
|---|---|---|
| `forsamlingar` | `lkfkod` | `namn` |
| `ekonomiska_enheter` | `skpkod` | `namn` |
| `kontrakt` | `kkkod` | `namn` |
| `stift` | `skod` | `namn` |

Övriga properties: `descriptio`, `name` (oftast tomma).

### Aggregering 2008-2014 vs 2018+

Äldre årgångar (2008-2014) lagrar **varje polygon-del som en separat
feature** med samma `lkfkod`. T.ex. har 2008 5010 features fördelade på
1888 unika `lkfkod`. Nyare årgångar (2018+) använder MultiPolygon med en
feature per kod.

För konsekvent jämförelse mellan år: aggregera per kod med
`shapely.ops.unary_union`:

```python
from collections import defaultdict
from shapely.ops import unary_union

groups = defaultdict(list)
for rec in sf.shapeRecords():
    code = rec.record.as_dict()[code_field]
    groups[code].append(shape(rec.shape.__geo_interface__))
features = [unary_union(geoms) if len(geoms) > 1 else geoms[0]
            for geoms in groups.values()]
```

### Mappning forsamling → pastorat

Det finns inget direkt fält som kopplar församling till pastorat -
relationen måste härledas geometriskt. Pastoratets polygon är unionen av
sina ingående församlingars polygoner, så centroid-inneslutning räcker:

```python
from shapely.strtree import STRtree
tree = STRtree([shape(p["geometry"]) for p in pastorat_features])
for f in forsamlingar_features:
    c = shape(f["geometry"]).centroid
    for idx in tree.query(c):
        if pastorat_shapes[idx].contains(c):
            # f tillhör pastorat[idx]
            break
```

## Användningsfall

- Visa församlingsgränser i en kart-applikation
  (se [`forsamlingskarta-leaflet/`](../../forsamlingskarta-leaflet/)).
- Hitta enklaver och exklaver
  (se [`forsamlingskarta-enklaver/`](../../forsamlingskarta-enklaver/)).
- Visa pastorats- och församlingsförändringar över tid
  (se [`forsamlingsindelning-historik/`](../../forsamlingsindelning-historik/)).
- GIS-analyser (vilka adresser tillhör vilken församling).

## Begränsningar

- Bara svenskt land - inga utlandsförsamlingar.
- WMS/WFS - inte ett REST-API. Klienter behöver kunna OGC-protokollen.
  Men zip-shapefile-vägen är ett bra alternativ för batch-jobb.
- Renderingen måste lösas själv (utöver det som GeoServer ger via WMS).
- Inget API som kopplar församling → pastorat. Måste härledas
  geometriskt (se ovan).
