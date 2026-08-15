# Kyrkobyggnadsregistret (KBR API)

REST-inspirerat API över byggnader (kyrkor + övriga byggnader) och
begravningsplatser ur Kyrkobyggnadsregistret.

## Snabbfakta

| Fält | Värde |
|---|---|
| Stil | REST (JSON eller XML via `Accept`) |
| Bas-URL prod | `https://api.svenskakyrkan.se/kbr/api/` |
| Bas-URL test | `https://api-t.svenskakyrkan.se/kbr/api/` |
| Version | v1 |
| Auth | `?apikey=` eller `SvkAuthSvc-ApiKey: <key>` |
| Doc | https://api.svenskakyrkan.se/doc/kyrkobyggnadsregistret/index.html |
| Verifierad | ✓ prod 2026-05-01 (Linköpings domkyrka, byggnad/32555 - invigd 1296, treskeppig kalkstensbyggnad) |

## Resurser

| Path | Funktion |
|---|---|
| `GET /byggnader` | Lista byggnader (kyrkor + övriga) |
| `GET /byggnad/{id}` | En byggnad på KBR-id (IdentitySVK) |
| `GET /begravningsplatser` | Lista begravningsplatser |
| `GET /begravningsplats/{id}` | En begravningsplats |

**OBS** Resursen heter `byggnader` (lista) men `byggnad` (singular). Båda
typerna (Kyrkor + Övriga byggnader) finns under `/byggnader` - separera
med `?kyrka=true|false`.

## Query-parametrar (gäller båda resurslistorna)

### Field selection

| Param | Funktion |
|---|---|
| `fields=*` | Alla fält |
| `fields=namn,id,pastorat` | Specifika fält |
| `fields=` saknas | Default = grundfält (`namn`, `id`) |

### Paging

| Param | Default | Range |
|---|---|---|
| `limit=N` | 10 | 3-100 |
| `offset=N` | 0 | - |

### Sortering

`orderby=<fält>` (suffix `-` för fallande, t.ex. `orderby=namn-`).

### Filter

| Param | Exempel | Funktion |
|---|---|---|
| `kyrka=true\|false` | `kyrka=true` | Bara kyrkor / bara övriga |
| `namn=<str>` | `namn=linköpings domkyrka` | Exakt namn (URL-encoda mellanslag) |
| `namn=~<str>` | `namn=~mora` | Innehåller (matchar `Hedemora`, `Bollmora`...) |
| `namn=^<str>` | `namn=^mora` | Börjar med |
| `id=N,N,N` | `id=34368,32555,32494` | Flera id-träffar |
| `andraddatum=YYYYMMDD-` | `andraddatum=20240101-` | Från datum |
| `andraddatum=YYYYMMDD-YYYYMMDD` | `andraddatum=20131201-20131231` | Intervall |
| `skapaddatum=...` | dito | Skapelsedatum |
| `agandeenhet=<namn>` | `agandeenhet=~linköping` | Ägare (stöder `~`/`^`) |
| `agandeenhetlkf=N,N` | `agandeenhetlkf=058001,058033` | Ägare per LKF-kod |
| `nuvarandefunktion=~kapell` | dito | Funktion (stöder `~`/`^`) |
| `testdata=true` | - | Returnerar fullt fältexempel mot testmiljön |

## Curl-exempel

```bash
export APIKEY='din-svk-api-nyckel'
BASE='https://api.svenskakyrkan.se/kbr/api'

# Linköpings domkyrka (id 32555) med alla fält
curl -s "${BASE}/byggnad/32555?fields=*&apikey=${APIKEY}" | jq

# Första 20 kyrkorna med utvalda fält
curl -s "${BASE}/byggnader?kyrka=true&limit=20&fields=namn,id,pastorat,stift&apikey=${APIKEY}" | jq

# Sök byggnader vars namn börjar med "mora"
curl -s "${BASE}/byggnader?namn=^mora&apikey=${APIKEY}" | jq

# Byggnader ändrade efter 2024-01-01
curl -s "${BASE}/byggnader?andraddatum=20240101-&fields=namn,id,andraddatum&apikey=${APIKEY}" | jq

# Alla kapell
curl -s "${BASE}/byggnader?nuvarandefunktion=~kapell&fields=namn,nuvarandefunktion&limit=100&apikey=${APIKEY}" | jq

# Begravningsplatser i Linköpings kommun (058033 = Linköping)
curl -s "${BASE}/begravningsplatser?agandeenhetlkf=058033&fields=*&apikey=${APIKEY}" | jq

# Hämta ren testdata för att se fullständig fältstruktur
curl -s "https://api-t.svenskakyrkan.se/kbr/api/byggnader?fields=*&testdata=true&apikey=${APIKEY}" | jq '.[0]'
```

## Felkoder

Standard HTTP, men body innehåller förklaring vid 400:

| Kod | Betydelse |
|---|---|
| 200 | OK, resultatet i body (JSON eller XML beroende på `Accept`) |
| 400 | Bad Request - body med felförklaring, t.ex. `{"message":"Otillåtet värde för byggnadsid! ..."}` |
| 401 | Unauthorized - saknad eller fel API-nyckel |
| 404 | Not Found - resurs med givet id finns inte |
| 500 | Internt serverfel - vänta och försök igen |

## Datastruktur

Två typer under `/byggnader`:

- **Kyrkor** (`kyrka=true`) - alla fält nedan.
- **Övriga byggnader** (`kyrka=false`) - bara ett delmängd basfält.

En byggnad **kan byta typ** via redigering i KBR - därför samma path för
båda. Begravningsplatser har ett enhetligt fältset.

Testmiljön (`api-t`) kräver kyrknätanslutning - `fields=*&testdata=true`
fungerar inte utifrån. Fältreferensen nedan är verifierad mot prod 2026-05-03.

### Fält - kyrkobyggnad (`fields=*`)

Verifierat mot Linköpings domkyrka (id 32555) och Abilds kyrka (id 35789).
**Obs:** Inget arkitekt-fält finns trots att äldre dokumentation antyder det.

| Fält | Typ | Beskrivning |
|---|---|---|
| `id` | int | KBR-id (IdentitySVK) |
| `namn` | str | Byggnadens namn |
| `kyrka` | bool | true = kyrka, false = övrig byggnad |
| `stift` | str | Stift (t.ex. "Linköpings stift") |
| `pastorat` | str | Pastoratkod (numerisk sträng, t.ex. "020101") |
| `agandeEnhet` | str | Ägande enhetens namn |
| `agandeEnhetLkf` | str | LKF-kod för ägande enhet |
| `agarkategori` | str | Ägarkategori (t.ex. "Svenska kyrkan") |
| `geografiskEnhet` | str | Geografisk enhets namn |
| `geografiskEnhetLkf` | str | LKF-kod för geografisk enhet |
| `lan` | str | Länets namn |
| `tatort` | str | Tätortstyp (t.ex. "Större stad", "Mindre tätort") |
| `xKoordinat` | int | Easting, SWEREF99TM (EPSG:3006) |
| `yKoordinat` | int | Northing, SWEREF99TM (EPSG:3006) |
| `fastighetsbeteckning` | str | Fastighetsbeteckning |
| `nuvarandeFunktion` | str | Funktion, kommaseparerat (se enum nedan) |
| `nuvarandeAnvandning` | str | Nuvarande användning (se enum nedan) |
| `ursprungligAnvandning` | str | Ursprunglig användning |
| `annanAnvandning` | str | Annan användning, pipe-separerat (se nedan) |
| `anpassningAnnanAnvandning` | str | Anpassning för annan användning, pipe-sep. |
| `anvandningsfrekvens` | str | Användningsfrekvens (t.ex. "Daglig användning", "Visstidsanvändning – hela året") |
| `oppenforhallande` | str | Öppethållande (t.ex. "Öppen och bemannad", "Nyckelöppen") |
| `invigning` | int | Invigningsår |
| `nybyggnadFran` | int | Byggnadstart (äldsta kända byggfas) |
| `byggarea` | int | Byggnadsarea (m²) |
| `planform` | str | Planlösning (t.ex. "Treskeppig", "Ej utrett") |
| `takform` | str | Takform (t.ex. "Sadeltak") |
| `takvinkel` | str | Takvinkel |
| `materialStomme` | str | Stommaterial |
| `materialFasad` | str | Fasadmaterial |
| `skyddEnligtKML` | str | Skyddsklassning |
| `identitetRAA` | str | BBR-id (RAÄ:s Bebyggelseregister), 14 siffror. Slå upp i Kringla med `https://www.kringla.nu/kringla/objekt?referens=raa/bbr/{identitetRAA}`. **Obs:** är inte samma som OSM:s `ref:se:raa` som avser fornlämningsnummer. Datakvaliteten i KBR är inte garanterad - se "Kända datafel" nedan. |
| `teleslinga` | str | Hörselslinga (t.ex. "Teleslinga finns") |
| `tillganglighetsanpassning` | str | Tillgänglighetsgrad |
| `handlingsprogramTillganglighet` | str | Handlingsprogram tillgänglighet |
| `facilityPartId` | UUID | UUID-referens till annat system (matchar **inte** Platser-API v4) |
| `skapadDatum` | ISO 8601 | Skapad i KBR |
| `andradDatum` | ISO 8601 | Senast ändrad i KBR |
| `annanAnvandningKommentar` | str | Fritext om annan användning |
| `anvandningsfrekvensKommentar` | str | Fritext om frekvens |
| `oppenforhallandeKommentar` | str | Fritext om öppethållande |
| `tillganglighetsanpassningKommentar` | str | Fritext om tillgänglighet |

### Enum: `nuvarandeAnvandning` (verifierat 2026-05-03, n=3465)

| Värde | Antal |
|---|---|
| Kyrka - gudstjänstkyrka | 3153 |
| Kyrka - förrättningskyrka | 206 |
| Kyrka - musik- och evenemangskyrka | 27 |
| Kyrka - visningskyrka | 23 |
| Används inte | 19 |
| Annan | 19 |
| Kyrka - samarbetskyrka | 13 |
| Kyrka – profant sambruk | 3 |
| Kyrka – profant bruk | 2 |

Obs: "vinterkyrka" är inte ett eget värde i detta fält - vinterkyrkor
klassas förmodligen som gudstjänstkyrka med låg `anvandningsfrekvens`.

### Enum: `nuvarandeFunktion` (urval)

Kommaseparerat, kombinationer förekommer. Verifierade exempel:

- `Kyrka, kapell`
- `Församlingshem, Kyrka, kapell`
- `Krematorium, Kyrka, kapell`
- `Administrationsbyggnad - församlingsexpedition, Barn - och ungdomslokal, Kyrka, kapell`

### Multipla värden i fält

Pipe-separerat (`|`):

- `annanAnvandning` - t.ex. `Konfirmationsarbete|Musikevenemang|Visningsverksamhet`
- `anpassningAnnanAnvandning` - t.ex. `Barnverksamhet|Toaletter,kapprum`

### Fält-introspektion

```bash
# Hämta default-fält (bara namn + id)
curl -s "${BASE}/byggnader?limit=1&apikey=${APIKEY}" | jq '.[0] | keys'

# Alla fält på en specifik byggnad
curl -s "${BASE}/byggnad/32555?fields=*&apikey=${APIKEY}" | jq 'keys'
```

## Kringla-uppslag via `identitetRAA`

Fältet är ett BBR-id ur Riksantikvarieämbetets Bebyggelseregister och
kan slås upp direkt i Kringla:

```bash
# Vadstena klosterkyrka (KBR id 32494)
curl -s "${BASE}/byggnad/32494?fields=id,namn,identitetRAA&apikey=${APIKEY}" | jq
# -> "identitetRAA": "21400000148207"
# -> https://www.kringla.nu/kringla/objekt?referens=raa/bbr/21400000148207
```

Användbart för att länka KBR-objekt vidare till antikvariska
beskrivningar, foton och fornlämningskontext via RAÄ.

## Kända datafel

KBR:s data är inmatat manuellt och kvaliteten varierar. Bekräftade fel
(2026-05-12):

- **Linköpings domkyrka (id 32555)** har `identitetRAA = 21400000577362`,
  vilket i Kringla pekar på **Östra Hargs kyrka**. Samma BBR-id ligger
  också på Östra Hargs egen post (KBR id 32446) - alltså en dubblett
  där domkyrkans rätta BBR-id saknas. Koordinaterna för domkyrkan har
  också observerats vara fel i tidigare utforskningar.

Verifiera alltid `identitetRAA` mot Kringla innan användning i produktion,
särskilt för enstaka högprofilbyggnader.

## Användningsfall

- Visa info om kyrkobyggnaden för en besökare på församlingens hemsida.
- Bygg upp register över skyddsvärda kyrkor och deras inventarier.
- Geografisk analys av kyrkobyggnader (i kombination med Platser/Församlingskartor).
- Underhållsplanering ("vilka byggnader är ändrade senaste året?").
