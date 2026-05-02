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

### 5. Kyrkokarta i webbläsaren (`forsamlingskarta-leaflet/`) ✅ Funktionell

Leaflet + OSM-karta som hämtar församlingsgränser via shapefile-zip
(direkt från `api.svenskakyrkan.se/kartor/`, inte WMS). Klustrade
plats-markörer per typ, dynamisk inladdning vid pan/zoom, automatisk
växling mellan stift / kontrakt / ekonomiska enheter / församlingar
baserat på zoom (manuell override via radio-väljare).

### 5b. Enklav- och exklavrundtur (`forsamlingskarta-enklaver/`) ✅ Funktionell

Identifierar alla församlingar med åtskilda del-polygoner (exklaver) och
helt inneslutna polygoner i grannförsamling (enklaver). 270 exklaver, 0
enklaver med 10 m simplifiering. UI med rundtur-knappar; aktiv
församlings delar i typ-färg (guld/vinröd), andra församlingar dimmas
till mörkgrön. Huvuddelen ritas alltid streckad så hela bilden syns även
när huvuddelen råkar vara territorialvatten (Nättraby-Hasslö).

### 5d. SVK ↔ OSM kyrkokonsistens (`osm-konsistenscheck/`) ✅ Funktionell + deployad

Live på <https://armandur.github.io/svk-api-playground/osm-konsistenscheck/>,
byggs dagligen 04:00 UTC av GitHub Actions.

Jämför kyrkor i SVK Platser-API:t mot OpenStreetMap. Matchar SVK och
OSM-pin via greedy global närmsta-granne (med tie-break på
namnlikhet) inom 100 m radie. Resultat: 3433 matchade, 978 bara SVK
(saknas i OSM), 1773 bara OSM (frikyrka eller fel taggning).

UI: pie-chart-kluster med fördelning per kategori, sökruta med lazy-load,
sub-filter för namn-mismatch / >50 m / OSM-taggbrist, OSM-denomination-
filter, avståndslinjer mellan SVK- och OSM-positioner, hybridlager
(satellit + labels) för verifiering, popup-länkar till SVK plats-sida,
iD-editor för redigering/tilläggning, CSV-export av "Bara SVK". Knapp
"Hämta nytt data" i headern triggar rebuild av SVK + OSM + Wikidata +
diff via `/osm-konsistenscheck/api/rebuild`-endpointen i `serve.py` med
pulserande live-status per steg, och färskhetsrad visar
`Senast uppdaterad: YYYY-MM-DD HH:MM` baserat på `built_at` i
`diff_summary.json`.

Wikidata-cross-check: `build_wikidata.py` hämtar via SPARQL alla Q-IDs
som har P708 (diocese) satt till ett av de 13 SvK-stiften (~8900 st).
`build_diff` berikar sedan `osm_only`-features vars `wikidata`-tagg
matchar med `likely_svk_miss=true`. UI visar dem med vinröd ring runt
blå pin + filter-toggle "Visa bara förmodliga SVK-missar". 178 av 1773
osm_only-noder identifierade så - mest "lutheran"-taggade och utan
denomination, dvs troliga missar i SVK Platser snarare än frikyrkor.

Datafix: dedup av SVK-poster på exakt samma koord (77 fall som "Trons
kapell Mo" + "Mo kyrka" på samma punkt blev tidigare två separata
matchningsförsök). OSM-Overpass-query utökad med `building=church/chapel`
eftersom många kyrkbyggnader saknar `amenity=place_of_worship`. OSM-
taggbrist-detektion ger 418 matchade där OSM saknar amenity, religion
eller korrekt denomination - alla har förslag på taggar i popup.

### 5c. Pastorat & församlingar över tid (`forsamlingsindelning-historik/`) ✅ Funktionell

Tidsslider 2008-2026 över både `ekonomiska_enheter` (pastorat) och
`forsamlingar`. Drawer (öppnas via (i)-knapp i slidern) listar nya
pastorat med ingående församlingar, **bildade pastorat** (FörE som blir
flerförsamlings-pastorat), ändrad sammansättning, upplösta pastorat,
**FörE som upphör**, **pastorat sammanslagna till FörE**, namnbyten och
församlingsändringar. Highlight-färgning av aktiva förändringar (grönt /
guld / mörkrött), toggle "Bara ändrade", klick-på-rad-zoomar-till-feature,
tickmarks på slidern, canvas-rendering + prefetch av angränsande år för
snabba sliderbyten.

Mappning forsamling→pastorat härleds geometriskt via STRtree +
centroid-inneslutning. Datakvalitet-filter: ignorerar genitiv-s
(`Tierp` ≡ `Tierps`) och suffix-tillägg (`Bromma` ≡ `Bromma församling`,
2015-reformen) men behåller terminologi-byten (`X kyrkliga samfällighet`
→ `X pastorat`, 2013-2014-reformen).

### 7. KBR-tidslinje (`kbr-tidslinje/`) ✅ Funktionell + deployad

Live på <https://armandur.github.io/svk-api-playground/kbr-tidslinje/>,
byggs dagligen av GitHub Actions (datat ändras sällan - cachelagras mellan
push-körningar, byggs alltid om vid daglig schedule).

Animerad karta med ~3 500 kyrkobyggnader ur KBR. Slider 1000-2025 med
play/pause. Kyrkor visas som streckad ikon ("under byggnation") vid
`nybyggnadFran`, fylld era-specifik ikon vid `invigning`. 6 epoker med
egna kyrksymboler och färger.

**Epoker och ikoner:**
- Medeltid (<1527): fristående klockstapel + enkel stenkyrka med sadeltak
- Reformationen (1527-1720): smal nålspira, oktagonalt tornöverstycke
- 1700-tal (1720-1800): klotfinal, pyramidformad tornkap
- 1800-tal (1800-1900): hög gotisk spira, spetsbågefönster (dominant epok: 852 kyrkor)
- 1900-tal (1900-2000): platt tornkrön, funktionalistisk
- 2000-tal (2000+): böljande tak, flytande kors

**Notering om koordinater:** SWEREF99TM via pyproj. Enstaka poster i KBR
har felaktiga koordinater (t.ex. Linköpings domkyrka ~11 km fel). Se
TODO om koordinatfellista nedan.

**Återstår:**

- **Bättre kyrksymboler** - rita om SVG-ikonerna i ett riktigt vektoritverktyg
  (Inkscape eller Figma). Nuvarande är ritade som inline-SVG-paths "i koden".
  Riktlinjer för design:
  - Silhuettbaserade - ska läsas som form, inte beroende av färg
  - Funka i båda lägena: fylld (invigd) och streckad kontur (under byggnation)
  - Ankar i botten-mitten, ikonstorlek 22×30 px
  - Låg path-komplexitet (1-3 element per form), annars blir det suddigt litet
  - **Medeltid:** fristående klockstapel (tresidig trätimmerstruktur med liten
    pyramidspets) + fristående stenkyrka (rektangulär med enkelt sadeltak,
    inga torn). Referens: Gamla Uppsala kyrka, Husaby kyrka.
  - **Reformationen:** Rektangulärt kyrkoskepp med något högre mittparti,
    enkel spira. Få nya kyrkor byggdes - ikonen signalerar stilleståndet.
  - **1700-tal:** Klassicistisk proportionering. Torn med klockvåning och
    knopp/glob-final. Symmetric fasad. Referens: Hedvig Eleonora kyrka.
  - **1800-tal:** Nygotisk - mycket hög och smal spira (ofta i tegel),
    spetsbågiga fönster på långhusets sida. Dominant era. Referens:
    Oscar Fredriks kyrka, Sofia kyrka.
  - **1900-tal:** Nationalromantik (rundtorn, tunga murverk) eller
    funktionalism (tegeltorn, platt krön). Referens: Engelbrektskyrkan,
    Kungsholms kyrka.
  - **2000-tal:** Samtida - rektangulär volym, böljande/kurvilineärt tak,
    fristående kors. Referens: Fisksätra kyrka, S:t Görans kyrka.

- **Koordinatfellista** - jämför KBR-koordinater mot Platser-API via
  `facilityPartId` (GUID-länken mellan systemen). Exportera kyrkor med
  >500 m avvikelse som CSV för rapportering till kyrkobyggnadsavdelningen
  på kyrkokansliet.

- **Stift-filter** - dropdown för att filtrera på ett stift.

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
| KBR | ✓ prod | Används i `kbr-tidslinje/`. Koordinater i SWEREF99TM. |
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
