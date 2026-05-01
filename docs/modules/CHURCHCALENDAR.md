# Kyrkoåret + bibeltexter (`webapi/api-v2/churchcalendar`)

Internt webb-API som driver `/kyrkoaret/bibeltexter`-sidan på
svenskakyrkan.se. Levererar **både** kyrkohögtider, liturgisk färg,
kyrkoårsdel **och** bibeltexterna i en och samma respons - täcker alltså
både portalkatalogens "Kyrkoåret" och "Kyrkoårets bibeltexter".

## Snabbfakta

| Fält | Värde |
|---|---|
| Stil | REST (JSON), enbart GET |
| Bas-URL | `https://www.svenskakyrkan.se/webapi/api-v2/` |
| Auth | `?apiKey=<uuid>` (queryparam, kamelKas) |
| Publik nyckel | `139ff33b-4451-4f0f-b397-1f4ec9307a87` (exponerad i webbplatsens JS) |
| Doc | Saknas - upptäcktes via reverse-engineering av webbplatsen |

Inga andra paths under `/webapi/api-v2/` har hittats publikt - allt annat
gav 404 vid scanning 2026-04-30.

## Endpoint

```
GET /churchcalendar[/{year}]
```

- **Utan år** - returnerar **innevarande kyrkoår** (startar 1:a advent
  föregående kalenderår). T.ex. anrop 2026-04-30 utan år returnerar
  perioden 2025-11-30 till 2026-11-22.
- **Med år** - `?year=2025` ger kyrkoår 2026 (samma data som default
  ovan). `year` mappar alltså mot **kalenderåret då 1:a advent inföll**,
  inte mot själva kyrkoårsnumret. Verifierat 2026-04-30.

## Curl-exempel

```bash
KEY='139ff33b-4451-4f0f-b397-1f4ec9307a87'

# Innevarande kyrkoår (default)
curl -s "https://www.svenskakyrkan.se/webapi/api-v2/churchcalendar?apiKey=${KEY}" | jq 'length'
# => 66

# Specifikt år
curl -s "https://www.svenskakyrkan.se/webapi/api-v2/churchcalendar/2025?apiKey=${KEY}" | jq '.[0]'

# Bara namn + datum + liturgisk färg
curl -s "https://www.svenskakyrkan.se/webapi/api-v2/churchcalendar/2025?apiKey=${KEY}" \
  | jq '[.[] | {feastName, startDate, liturgicalColor}]'

# Hitta alla högtider med röd färg
curl -s "https://www.svenskakyrkan.se/webapi/api-v2/churchcalendar/2025?apiKey=${KEY}" \
  | jq '[.[] | select(.liturgicalColor == "Red") | {feastName, startDate}]'
```

## Datastruktur

JSON-array med 66 entries per kyrkoår. Varje entry:

```jsonc
{
  "type": "Första_advent",
  "id": 12,
  "feastName": "Första söndagen i advent",
  "feastText": "Den första söndagen i advent berättar om...",
  "feastHeading": "Ett nådens år",
  "otherName": "",
  "startDate": "2025-11-30T00:00:00",
  "endDate": "2025-11-30T23:59:59",
  "annualId": 3,                       // 1 eller 3 (årgång)
  "annualText": "Årgång 3",
  "isHolyWeek": false,
  "liturgicalColor": "White",          // se enum nedan
  "liturgicalColorDisplay": "Vit - byte till violett/blå efter kl 18",
  "churchYearPart": {
    "yearPart": "Advent",
    "id": 1,
    "name": "Advent",
    "startTime": "2025-11-30T00:00:00",
    "endTime": "2025-12-21T23:59:59",
    "description": "Ordet advent betyder ankomst...",
    "liturgicalColorID": 1,
    "altarCandlesID": 6
  },
  "readings": {
    "feastId": 12,
    "name": "Första advent",
    "readings": [
      {
        "readingType": "Gammaltestamentlig",
        "årgång": 3,
        "acronyme": "Sak 9:9-10",
        "acronymeFull": "Sakarja kapitel 9, vers 9-10",
        "text": "Ropa ut din glädje, dotter Sion, ..."
      }
      // ... episteltext, evangelium, psaltarpsalm m.fl.
    ]
  },
  "altar": { /* dukningsinfo */ },
  "state": { /* statusflaggor */ }
}
```

### `liturgicalColor` - enum

`White`, `Violet`, `Red`, `Green`, `Black`, `Blue`, `VioletOrBlue`,
`GreenOrBlue`, `GreenOrWhite` (de sista tre används när färgen ändras
under dygnet).

### `annualId` - årgång

Värden: `1` eller `3`. Svenska kyrkan använder en treårig läsårscykel
men i den nuvarande boken finns texterna för årgång 1 och 3 (årgång 2
infaller på helger som inte ingår). Använd `annualText` för
display-värde ("Årgång 3").

### `churchYearPart`

Övergripande indelning av kyrkoåret: Advent, Jul- och nyårstid, Trettondedagstiden,
Fastan, Påsken, Pingst, Trefaldighetstiden m.fl. Varje period har egen
liturgisk grundfärg och antal altarljus.

## Användbart för

- Visa kyrkoåret i kalender-app eller webbsida.
- Auto-välja liturgisk färg för ett datum.
- Slå upp dagens bibeltexter för andakt/predikan.
- Bygga hjälpverktyg för kyrkoanställda.

## Begränsningar

- Skickar alltid hela året - ingen filtrering på datum eller högtid.
- Endast GET. Skrivande förekommer inte (det är en redaktionell källa).
- API-nyckeln är *publik klientside-nyckel*, men det är en obligatorisk
  parameter - utan den blir det 401/403.
- Saknar officiell doc - om brytande ändringar sker märks de bara genom
  att webbplatsen slutar fungera.
