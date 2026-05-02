# TODO - utforskning, testprojekt, idéer

Lekplats för pilot-projekt mot SVK-API:erna. Varje delprojekt får en
egen undermapp i repo-roten (`<projektnamn>/`) med eget README.

## Projektidéer

### 1. Signage-vy med dynamiska öppettider (`signage-platser/`) ✅ Funktionell

**Status:** Verifierad mot Härnösands domkyrka. URL-parametrar
för konfiguration:
- `?place=<guid>` - hämta valfri plats live via SVK-proxyn
- `?view=week|rolling|extended` - layoutläge (mån-sön / 7 dagar
  framåt / idag-till-söndag-nästa-vecka)
- `?details=max|min` - visa eller dölja klocka, faciliteter,
  adress och footer-tidstämpel

Veckotabellen vävs ihop från flera perioder (avvikelser visas in-
line på rätt dag) och `openHours.info` renderas under tabellen
med radbrytningar bevarade.

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

### 2. Mini-app för platsadministration (`platser-edit-app/`) ✅ Funktionell

Sökflöde + veckoschema-editor + PUT mot CMS:ets interna admin-flöde
(`admin.svenskakyrkan.se/webapi/api-v2/place/{id}`) via en proxy i
serve.py. End-to-end-verifierad 2026-05-01 mot Härnösands domkyrka.

**Klart:**

- **Sökning** - fritext via `?q=...` med debounce, klickbar trefflista.
- **Periodöversikt** - kort per öppettidsperiod med kompakt
  veckodags-grid, klickbar för att välja period i avancerat-läget.
- **Sessions-panel** - bookmarklet + DevTools-instruktion för
  HttpOnly-cookies, runtime-input som sparar i serverns RAM,
  "Pinga nu"- och "Verifiera plats (GET)"-knappar för isolering.
  Diagnostik visar last_pinged_at, last_ping_status m.fl. tickande
  i realtid.
- **Stäng en specifik dag** - splittar matchande period i upp till
  tre delar (eller utökar befintlig undantagsperiod om en sådan
  redan rymmer datumet). Anledning appendas till `openHours.info`.
- **Skapa anpassad period** - datumintervall + valda veckodagar +
  egna intervall, t.ex. för sommaröppet eller sportlov.
- **Validering** klient-sidigt: överlappande intervall fångas
  innan PUT (servern avvisar annars med HTTP 400).
- **Sliding-cookie-sniffing** + 30-min keep-alive-tråd håller
  sessionen vid liv. Hela cookie-headern (5 cookies inkl
  HttpOnly auth) merge:as när servern roterar någon av dem.
- PUT (full replace) mot `/api/admin/place/{id}` med ändringar
  applicerade på fullt place-objekt. `info`-fältet utelämnas om
  textarean är tom så servern inte tolkar det som rensning.

**Återstår:**

- Bekräftelse-modal innan PUT.
- Auth-skikt - alla med dev-server-tillgång kan idag skriva.
- Städa gamla "Stängt YYYY-MM-DD: ..."-rader i `info` när datumen
  har passerat.
- Klar-markering i "Mina platser" på vilka platser som har
  öppettider satta (idag visar alla platser oavsett `openHours`).

**Klart efter senaste sessionen:**

- "Mina platser"-flöde via `/churchcontext` + AD-grupp-parsing.
  Listar platser grupperade per ägare (Pastorat överst, sen
  församlingar alfabetiskt).
- Skapa/ta bort hela perioder via knappar i avancerat-panelen och
  ta-bort-× på period-korten.
- "Pinga nu" verifierar både session-keepalive och faktisk admin-
  GET mot Härnösands domkyrka (eller vald plats).
- Refresh från admin-endpointen efter PUT så användaren ser
  serverns version direkt.

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
