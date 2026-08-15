# K-samsök (SOCH) - Riksantikvarieämbetet

Aggregator-API över **cirka 10 miljoner kulturarvsobjekt** från svenska
minnesinstitutioner. Inkluderar BBR (Bebyggelseregistret),
fornminnesinformation (lamning/FMIS), arkivdokumentation, museiföremål
och historiska foton. Drivs av Riksantikvarieämbetet (RAÄ) - är alltså
**inte** ett Svenska kyrkan-API, men kompletterar [KBR](KBR.md) eftersom
KBR:s `identitetRAA` är just ett BBR-id som kan slås upp här.

## Snabbfakta

| Fält | Värde |
|---|---|
| Stil | REST med CQL-frågespråk |
| Bas-URL | `https://kulturarvsdata.se/ksamsok/api` |
| Persistent URI | `https://kulturarvsdata.se/{institution}/{tjänst}/{id}` (t.ex. `raa/bbr/21400000148207`) |
| Auth | **Öppet, ingen nyckel krävs**. CC0-licens på metadata. |
| Returformat | XML (default), JSON-LD (`Accept: application/json` eller `/jsonld/` i path), RSS |
| Teckenkodning | UTF-8 enbart |
| Doc | https://www.raa.se/hitta-information/k-samsok/att-anvanda-k-samsok/ |
| Kontakt | ksamsok@raa.se |
| Verifierad | ✓ 2026-05-12 (search, persistent BBR-URI, getRelations) |

## Persistenta URI:s

Varje objekt har en stabil URI som returnerar RDF/XML eller JSON-LD direkt
utan att gå via `/ksamsok/api`. Mönstret är:

```
https://kulturarvsdata.se/{institution}/{tjänst}/{id}
```

Exempel:

| URI | Innehåll |
|---|---|
| `raa/bbr/21400000148207` | Vadstena klosterkyrka (Bebyggelseregistret) |
| `raa/lamning/2fcc7e00-359e-...` | En fornlämning (FMIS-arvet) |
| `raa/dokumentation/{uuid}` | Foto/skanning/PDF i Riksantikvarieämbetets arkiv |

**Koppling till KBR:** Fältet `identitetRAA` på en KBR-byggnad är ett
BBR-id som mappar 1:1 till `raa/bbr/{identitetRAA}` här. Se
[Korslänka KBR + K-samsök](#korslänka-kbr--k-samsök) nedan.

## Metoder

Alla metoder anropas via `?method=<namn>&version=1.1&...` mot
`https://kulturarvsdata.se/ksamsok/api`.

| Metod | Funktion | Obligatoriska parametrar |
|---|---|---|
| `search` | Fritextsökning / CQL, returnerar matchande objekt | `query` |
| `statistic` | Räkna unika värdekombinationer per index | `index` |
| `statisticSearch` | Statistik filtrerad av sökning | `index`, `query` |
| `facet` | Faceterad sökning | `index`, `query` |
| `searchHelp` | Auto-complete på indexvärden | `index` |
| `allIndexUniqueValueCount` | Antal unika värden per index för en query | `query` |
| `getServiceOrganization` | Info om bidragande institution(er) | `value` (`all` för alla) |
| `getRelations` | Listar relationer åt båda hållen | `objectId`, `relation` |
| `getRelationTypes` | Möjliga relationstyper | `relation` |
| `stem` | Visar ordstamsbehandling | `words` |
| `rss` | Som `search` men returnerar mediaRSS | `query` |

Utöver dessa finns en separat **UGC-Hub** för användargenererat innehåll
(Wikipedia, Wikimedia Commons, Europeana) - se RAÄ:s dokumentation.

## Query-parametrar (CQL)

`search` använder ett CQL-liknande språk. Grundfält:

| Fält | Funktion |
|---|---|
| `text` | Fritext över alla fält, med ordböjningar |
| `strict` | Som `text` men utan ordstamsbehandling |
| `item` | Sökning i objekt-/föremålsspecifika fält |
| `place` | Plats-/geografifält |
| `time` | Tid/datering |
| `actor` | Personer/organisationer |
| `itemKeyWord` | Nyckelord (t.ex. `Byggnadsminnen:Statl`, `Riksintressen`) |
| `itemType` | Objekttyp |
| `boundingBox` | Geografisk avgränsning (se nedan) |
| `serviceName` | Datakällans tjänstenamn (t.ex. `bbr`, `lamning`, `arkiv-dokument`) |

Kombineras med `AND`, `OR`, `NOT`:

```
query=item="sten yxa" AND place=gotland NOT itemMaterial=brons
```

### Geografi

`boundingBox` stöder WGS84, SWEREF99 och RT90. Formatet är:

```
boundingBox=/<system>%20"<minLng>%20<minLat>%20<maxLng>%20<maxLat>"
```

Exempel (Lund):

```
query=boundingBox=/WGS84%20"12.883397%2055.56512%2013.01874%2055.635582"
```

### Paginering och sortering

| Param | Default | Range |
|---|---|---|
| `hitsPerPage` | 25 | max 500 |
| `startRecord` | 1 | - |
| `sort` | (relevans) | indexnamn |
| `sortConfig` | - | `desc`/`asc` |

### Returformat

`recordSchema=rdf` (default), `presentation` (förenklad XML) eller
`xml&fields=...` (egna fält). JSON-LD fås via:

```bash
curl -H "Accept: application/json" https://kulturarvsdata.se/raa/bbr/21400000148207
# eller
curl https://kulturarvsdata.se/jsonld/raa/bbr/21400000148207
```

## Curl-exempel

```bash
BASE='https://kulturarvsdata.se/ksamsok/api'

# 1. Enkel fritextsökning
curl -s "${BASE}?method=search&version=1.1&hitsPerPage=5&query=text=runsten"

# 2. Sökning per fält + boolesk kombination
curl -s -G "${BASE}" \
  --data-urlencode "method=search" \
  --data-urlencode "version=1.1" \
  --data-urlencode "hitsPerPage=10" \
  --data-urlencode 'query=item="sten yxa" AND place=gotland'

# 3. Geo-sökning (boundingBox runt Visby)
curl -s -G "${BASE}" \
  --data-urlencode "method=search" \
  --data-urlencode "version=1.1" \
  --data-urlencode 'query=boundingBox=/WGS84 "18.27 57.62 18.32 57.65"'

# 4. Hämta ett objekt direkt via persistent URI (RDF/XML)
curl -s "https://kulturarvsdata.se/raa/bbr/21400000148207"

# 5. Samma objekt som JSON-LD
curl -s -H "Accept: application/json" \
  "https://kulturarvsdata.se/raa/bbr/21400000148207" | jq '.["@graph"][0]'

# 6. Lista alla relationer för en byggnad (foton, dokument, fornlämningar)
curl -s "${BASE}?method=getRelations&version=1.1&relation=all&objectId=raa/bbr/21400000148207"

# 7. Bara bildrelationer (isVisualizedBy)
curl -s "${BASE}?method=getRelations&version=1.1&relation=isVisualizedBy&objectId=raa/bbr/21400000148207"

# 8. Statistik - hur många objekt per institution
curl -s "${BASE}?method=statistic&version=1.1&index=serviceOrganization"

# 9. Faceterad sökning - nyckelord för runstenar
curl -s "${BASE}?method=facet&version=1.1&query=text=runsten&index=itemKeyWord&removeBelow=10"
```

## Korslänka KBR + K-samsök

Eftersom `identitetRAA` i KBR är ett BBR-id kan vi gå från en
Svenska kyrkan-byggnad rakt in i Riksantikvarieämbetets fulla
beskrivning:

```bash
APIKEY='<svk-nyckel>'

# Steg 1: hämta BBR-id från KBR
BBR=$(curl -s "https://api.svenskakyrkan.se/kbr/api/byggnad/32494?fields=identitetRAA&apikey=${APIKEY}" \
        | jq -r '.identitetRAA')

# Steg 2: hämta full byggnadsbeskrivning från K-samsök (JSON-LD)
curl -s -H "Accept: application/json" "https://kulturarvsdata.se/raa/bbr/${BBR}" | jq '.["@graph"][0]'

# Steg 3: lista alla foton (länkar till pub.raa.se)
curl -s "https://kulturarvsdata.se/ksamsok/api?method=getRelations&version=1.1&relation=isVisualizedBy&objectId=raa/bbr/${BBR}"
```

**Datakvalitetsvarning:** Se [KBR - Kända datafel](KBR.md). Vissa
KBR-byggnader har felaktigt `identitetRAA`. Vid felmappning får man rätt
RDF-svar från K-samsök, men för fel byggnad. Verifiera mot Kringla
(`https://www.kringla.nu/kringla/objekt?referens=raa/bbr/{id}`) innan
användning i produktion.

## Kringla som klient

[Kringla](https://www.kringla.nu/) är RAÄ:s publika sök-UI ovanpå
K-samsök. Bra för snabbinspektion av ett enskilt objekt:

```
https://www.kringla.nu/kringla/objekt?referens=raa/bbr/21400000148207
```

`referens=` tar samma path som persistent-URI:n (utan `https://kulturarvsdata.se/`).

## Felkoder

| Kod | Betydelse |
|---|---|
| 200 | OK, XML/JSON i body |
| 400 | Bad Request - typiskt felaktig CQL eller saknad obligatorisk param |
| 404 | Persistent URI pekar på okänt objekt |
| 5xx | Backend-problem - vänta och försök igen |

## Datastruktur (kort)

K-samsök är RDF-baserat. Varje objekt är en `ksam:Entity` med:

- **Identitet:** `@id` = persistent URI, `serviceName`, `itemType`
- **Etiketter:** `itemLabel`, `itemTitle`, `itemName`
- **Plats:** `context` -> `placeName`, `countryName`, geo-koordinater (georss/gml)
- **Tid:** `fromTime`, `toTime` på Context-noder
- **Media:** `thumbnail`, `media` (länkar till `pub.raa.se`)
- **Licens:** `itemLicenseUrl`, `mediaLicense`
- **Relationer:** `describes`, `isVisualizedBy`, m.fl. (se `getRelationTypes`)

Namnrymder att känna igen i RDF/JSON-LD:

| Prefix | URI |
|---|---|
| `ksam` | `http://kulturarvsdata.se/ksamsok#` |
| `pres` | `http://kulturarvsdata.se/presentation#` |
| `georss` | `http://www.georss.org/georss#` |
| `gml` | `http://www.opengis.net/gml` |
| `dc` / `dcterms` | Dublin Core |
| `foaf` | FOAF |

## Användningsfall

- **Berika KBR med foton.** För varje SVK-byggnad med `identitetRAA`,
  hämta `isVisualizedBy`-relationer och länka miniatyrer.
- **Fornlämningar nära en kyrka.** Använd kyrkans SWEREF99TM-koordinater
  från KBR till en `boundingBox`-sökning på `serviceName=lamning`.
- **Kulturhistorisk kontext för Bönewebbens platser.** Hämta `lamning`-
  och `bbr`-objekt inom radie kring tända ljus och visa på kartan.
- **Statistik över byggnadsminnen per stift** genom korrelation mellan
  KBR:s `stift`-fält och K-samsöks `itemKeyWord=Byggnadsminnen:Statl`.

## Klienter och bibliotek

- **Abbe98/ksamsok-py** - Python-wrapper (https://github.com/Abbe98/ksamsok-py)
- **Abbe98/ksamsok-rest** - REST-proxy som ger JSON (https://github.com/Abbe98/ksamsok-rest)

## Vidare läsning

- Officiell startguide: https://www.raa.se/hitta-information/k-samsok/att-anvanda-k-samsok/kom-igang-med-k-samsoks-api/
- Metoder i detalj: https://www.raa.se/hitta-information/k-samsok/att-anvanda-k-samsok/metoder/
- Protokoll och parametrar: https://www.raa.se/hitta-information/k-samsok/att-anvanda-k-samsok/protokoll-och-parametrar/
- Kringla (UI ovanpå K-samsök): https://www.kringla.nu/
