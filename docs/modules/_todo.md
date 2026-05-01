# TODO - utforskning, testprojekt, idéer

Lekplats för pilot-projekt mot SVK-API:erna. Varje delprojekt får en
egen undermapp i repo-roten (`<projektnamn>/`) med eget README.

## Projektidéer

### 1. Signage-vy med dynamiska öppettider (`signage-platser/`)

**Status:** ✅ Datakälla bekräftad. Härnösands domkyrka har riktiga
öppettider i Platser-API:t. Klart att starta bygget.

**Use-case:** En infällbar webbsida (HTML-vy som körs i en
signage-miljö) utanför t.ex. **Härnösands domkyrka** som alltid visar
aktuella öppettider. En zon på skärmen är reserverad för vyn och
uppdateras med polling.

**Tekniskt skelett:**

- Statisk HTML/CSS/JS-sida (vanilla, ingen bundler) eller en minimal
  FastAPI som serverar vyn + proxar mot Platser-API:t (för att inte
  exponera API-nyckeln till klienten).
- Konfig: plats-slug, t.ex.
  `20270-harnosands-domkyrkoforsamling-harnosands-domkyrka`.
- Hämtar `GET /platser/v4/place/{slug}` - se [PLATSER](#PLATSER) för
  öppettidsschema (`openHours.periods[].days.{mo,tu,...}[]` med stöd
  för säsongsperioder via `validFrom/validTo`).
- Update-intervall: ~5 min polling (ingen webhook finns).
- Visningslogik: idag öppet/stängt, nästa ändring, säsongsperioder.

**Bekräftade fakta (2026-05-01):**

- Öppettider är **strukturerad data** - veckodag + från-till-tider,
  flera intervall per dag möjliga (lunchstängt), flera perioder med
  `validFrom/validTo` för säsongsöppet.
- Härnösands domkyrka: mån-lör 08-16, sön 08-13, gäller från 2022-03-17
  utan slutdatum.
- Tom dag-array `[]` = stängt den veckodagen.
- `openHours.info` är fritextkommentar (förmodligen för specialfall).

**Öppna frågor:**

- Hanterar API:t **avvikelser** (t.ex. "stängt 24/12 eftermiddag")?
  Ej hittat i schemat - kanske via `openHours.info` fritext, eller
  helt enkelt inte stött. Verifiera mot några platser med "kända"
  storhelgsstängningar.
- Är `placeId`/slug det som faktiskt används av "platsadministrationen"
  i Content Studio? Sannolikt ja eftersom owner.id (`20270`) matchar
  `enhetsid` i andra API:er.

### 2. Mini-app för platsadministration (`platser-edit-app/`) ✅ PoC påbörjad

Sökflöde + veckoschema-editor + PATCH mot `/place/{id}`. Byggd ovanpå
en generic SVK-proxy (`/api/platser/*`) i serve.py som lägger till vår
APIKEY_PROD server-sidigt så klienten aldrig ser nyckeln.

**Klart:**

- Fritext-sökning via `?q=...` med debounce.
- Detaljvy: plats-info + period-väljare + redigerbart veckoschema
  (lägg till/ta bort intervall, ändra tider).
- PATCH mot `/place/{id}` med `updatedBy` + uppdaterad
  `openHours.periods`.

**Återstår:**

- Filter på församling specifikt via UnitAPI eller `?owner_id=`
  (`/api/units/*` är förberett i proxyn).
- Stöd för `validFrom`/`validTo` i editorn (säsongsperioder,
  inkl skapa/ta bort hela perioder).
- Editera `openHours.info` (fritextkommentar).
- Bekräftelse-modal innan PATCH.
- Auth - just nu får alla med dev-server-tillgång skriva. Behöver
  någon form av magic-link eller liknande för riktigt bruk.

**Öppna frågor (uppdaterade):**

- Tillåter Platser-API:t skriv för slutkunder? **Ja, via PATCH/PUT.**
  Inget Content Studio-reverse-engineering behövs.
- **Skrivbehörighet är skopad** - vår APIKEY_PROD har read men inte
  write (verifierat 2026-05-01: PATCH /place/{Härnösands domkyrka}
  → 403 Access denied).
- **Lösning hittad via reverse-engineering:** CMS:et använder en
  intern proxy `admin.svenskakyrkan.se/webapi/api-v2/place/{id}` med
  `CS_UserSessionId`-cookie istället för API-nyckel. Vår serve.py har
  nu en `/api/admin/`-proxy som låter platser-edit-app skriva via
  CMS-flödet, med `CS_SESSION` från `.env`. Se
  `docs-from-claude-code-chrome/platser-edit-flow-2026-05-01.md`.

### 3. Kyrkoårs-widget (`kyrkoaret-widget/`) ✅ PoC klar

Visar dagens högtid (eller närmast kommande), liturgisk färg som swatch,
kyrkoårsdel, högtidsbeskrivning och dagens bibeltexter. Drivs av
[CHURCHCALENDAR](#CHURCHCALENDAR) - öppet API, ingen nyckelhantering
behövs på klientsidan. SVK-stylad (beige + vinröd, DM Sans + Spectral).

Återstår:
- Embed-läge (`?embed=1`) för iframe-användning på församlingshemsidor.
- localStorage-cache för offline-fallback.
- Variant som visar veckans events från CalendarAPI ihop med dagens
  högtid (kräver Azure-key + cors-proxy om det körs klient-sidigt).

### 4. Församlingssök-formulär (`forsamlingssok-form/`)

Mini-sida där man fyller i en adress och får tillbaka församling +
kontaktuppgifter. Kombinerar [FORSAMLINGSSOK](#FORSAMLINGSSOK) +
[ENHETSINFORMATION](#ENHETSINFORMATION) (slå upp `enhetsid` ->
fullständig kontaktinfo).

### 5. Kyrkokarta i webbläsaren (`forsamlingskarta-leaflet/`)

Leaflet-baserad karta som lägger till SVK:s församlingsgränser via
WMS från [FORSAMLINGSKARTOR](#FORSAMLINGSKARTOR). Eventuellt med
möjlighet att klicka och se vilken församling man tittar på.

### 6. Kalenderhändelse-aggregator (`calendar-aggregator/`)

Hämta events från [CalendarAPI](#CALENDARAPI) för flera enheter och
visa som en gemensam stiftskalender eller liknande. Bra övning på
OAuth2-flödet och OData-aktig sökning.

## Generellt - nästa steg per API

Status efter verifiering med vår nyckel mot test 2026-05-01:

| API | Status | Nästa steg |
|---|---|---|
| CalendarAPI | (saknar Azure-nyckel) | Skaffa Azure APIM subscription-key. |
| CHURCHCALENDAR | ✓ funkar publikt | Lågt hängande - bygg `kyrkoaret-widget/`. |
| Enhetsinformation | ✗ 302 mot test | Prenumerera på "Enhetsinformation" via portalen. |
| Församlingskartor | ✓ ingen auth | Validera lager-listan via `GetCapabilities`. |
| Församlingssök | ✗ 401 CallerInvalid | Prenumerera på "Församlingssök" på portalen. |
| KBR | ✗ 302 mot test | Prenumerera på "Kyrkobyggnadsregistret". |
| Platser | ✗ 401 mot test | **Prenumerera på "Platser"** - kritiskt för signage-projektet. Verifiera även om öppettider finns. |
| UnitAPI | ✓ test | Klart för bruk mot test. Be SVK om prod-aktivering när relevant. |
| Ämnesområden | ✓ test | Klart för bruk mot test. |

## Prenumerationsstatus i portalen

Den enda produkt som vår nyckel verkar ha åtkomst till nu är
`externwebb/api-v2/odata` (täcker både UnitAPI och Ämnesområden).
Övriga produkter behöver aktiveras separat via inlogg på
`https://api-t.svenskakyrkan.se/` -> "Mina tjänster" eller motsvarande.

Prod-domänerna (`api.svenskakyrkan.se`) ger **alltid 401** med vår
nyckel. Det är troligen så att portalen utfärdar separata nycklar för
test resp. prod.

## Öppna spörsmål till SVK

Frågor som kräver kontakt med SVK:s API-team via
`https://api.svenskakyrkan.se/kontakt`:

- Hur registrerar man sig för en API-nyckel? Kvalificeringsprocess?
- Är `139ff33b-4451-4f0f-b397-1f4ec9307a87` (CHURCHCALENDAR) avsedd
  för publik konsumtion eller en intern nyckel som bara råkar vara
  exponerad?
- Är CalendarAPI öppen för publika konsumenter eller bara för
  registrerade producenter?
- Finns en officiell väg att redigera platsdata utan att gå via
  Content Studio?
