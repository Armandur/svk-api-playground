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

#### Utökad data per källa i popupar och nya taggbristsignaler

Fälten nedan är verifierade mot respektive API 2026-05-03.
Kräver ändringar i `build_svk.py` (Platser), `build_kbr.py` (KBR)
och `build_diff.py` (taggbrist-logik) + `index.html` (visning).

**KBR - popup-kontext (lägg till i `build_kbr.py` fields-parametern)**

- `nuvarandeAnvandning` - nuvarande användning ("Kyrka - gudstjänstkyrka",
  "Kyrka - förrättningskyrka", "Används inte" m.fl.). Förklarar varför
  en prick är kbr_only eller ovanlig. Visa i KBR-sektionen i popupen.
- `oppenforhallande` - hur kyrkan hålls öppen ("Öppen och bemannad",
  "Nyckelöppen"). Besöksrelevant kontext i popupen.
- `anvandningsfrekvens` - hur ofta den används ("Daglig användning",
  "Visstidsanvändning – hela året"). Förklarar ovanliga kyrkor.
- `byggarea` - byggnadsarea i m². Storleksindikator i popupen.

**KBR - taggbristsignaler (kräver nya fält i `build_kbr.py` + diff-logik)**

- `teleslinga` = "Teleslinga finns" → föreslå `hearing_loop=yes` om OSM
  saknar det. Obs: korsar med Platser `hasHearingLoop` - kan kräva ett
  av de två.
- `tillganglighetsanpassning` = "Helt..." → `wheelchair=yes`,
  "Delvis..." → `wheelchair=limited`. Föreslå om OSM saknar `wheelchair`.
- `skyddEnligtKML` icke-tomt → föreslå `heritage=2` +
  `heritage:operator=Riksantikvarieämbetet` om OSM saknar `heritage`.
  (Vi visar redan skyddsvärdet i popupen men föreslår det inte som tag.)
- `identitetRAA` icke-tomt → föreslå `ref:se:raa=<värde>` om OSM saknar.

**Platser-API - popup-kontext (lägg till i `build_svk.py`)**

- `shortDescription` - kort fritexter om kyrkan. Visa i Platser-sektionen
  om den är ifylld (inte alltid).
- `visitingInfo.address` + `postalCode` - besöksadress (84%/69% ifyllt).
  Visa i popup. Används också som grund för addr-taggbrist nedan.
- `geolocationInfo.municipality` - kommunnamn. Komplement till `city`.

**Platser-API - taggbristsignaler (kräver nya fält i `build_svk.py` + diff-logik)**

- `visitingInfo.address` → föreslå `addr:street=X` om OSM saknar
  `addr:street`. Kräver parsning av gatunamn och husnummer ur adressfältet.
- `visitingInfo.postalCode` → föreslå `addr:postcode=X` om OSM saknar.
- `placeDetails.hasToilet = true` → föreslå `toilets=yes` om OSM saknar
  (56% av kyrkorna i samplet).
- `placeDetails.accessibility.hasHearingLoop = true` → `hearing_loop=yes`
  (43% av samplet). Korsar med KBR `teleslinga`.
- `placeDetails.accessibility.hasRamp = true` → `wheelchair=yes` om OSM
  saknar (14% av samplet, kan kombineras med KBR tillganglighetsanpassning).
- `placeDetails.accessibility.toiletAccessible = true` →
  `toilets:wheelchair=yes` om OSM saknar (13% av samplet).

**Idé: "Visa mer"-panel**

Knapp i popupen som öppnar ett sidopanel/modal med samtliga rådata
från alla tre källor för vald prick.

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

**Planerat: KBR som tredje koordinatkälla (ej påbörjat)**

Lägga till KBR som extra lager i befintlig karta. KBR-koordinater är
självregistrerade av kyrkan - OSM är oberoende fältverifierat, vilket
gör KBR↔OSM till den mest intressanta jämförelsen. KBR↔Platser visas
i popup men driver inte filtret (båda är SVK-interna, kan ha samma fel).
Se 8b för bakgrund och stickprov.

_Beslutade designval:_
- KBR visas som extra lager ovanpå befintlig karta (inte eget tab)
- KBR-kyrkor utan matchning (`kbr_only`) visas som standard
- Primärt kvalitetsmått: `kbr_osm_distance_m`
- Tröskel för koordinatfel: 200 m

_Implementationsplan:_

**1. `build_kbr.py` (ny fil)**

Hämtar KBR via `GET /kyrkobyggnadsregistret/byggnader?kyrka=true`
(samma endpoint som kbr-kvalitet), konverterar SWEREF99TM → WGS84
via pyproj, outputtar `data/kbr.geojson`. Fält per feature:
`kbr_id`, `namn`, `stift`, `lat`, `lng`, `skydd`.
Cachelagras i GitHub Actions-cache med `build_kbr.py`-hash som nyckel.
Kräver `APIKEY_PROD`-secret.

**2. `build_diff.py` - trevägsmatchning**

Ny fas efter befintlig SVK↔OSM-matchning. KBR matchas mot den samlade
poolen av OSM + Platser-punkter (de som redan finns i diff.geojson) via
`normalize_name()` + geografiskt närmaste kandidat inom 200 km cap.
Vid lika avstånd prioriteras OSM-punkt framför Platser-punkt.

Fyra utfall per KBR-kyrka:

1. **Matchar befintligt matched-par (Platser+OSM)** - berika med
   `kbr_lat/lng`, `kbr_osm_distance_m`, `kbr_platser_distance_m`
2. **Matchar osm_only** - stärker `likely_svk_miss`-flaggan; berika
   med KBR-koordinater och avstånd mot OSM
3. **Matchar svk_only** - berika, inget nytt signalvärde
4. **Ingen matchning** - lägg till som ny `kbr_only`-feature med
   orange markör; visas som standard i kartlagret

Nya fält i `diff_summary.json`:
- `kbr_matched`, `kbr_only_count`, `kbr_osm_errors_200m`

**3. UI - `index.html`**

Nytt toggle-lager "KBR" (på som standard). Visar:
- Orange markör för `kbr_only`-kyrkor med popup: namn, stift, skydd
- Orange markör + streckad linje KBR↔OSM för matched-par där
  `kbr_osm_distance_m > 200`, med avstånd i popup
- Sub-filter "KBR-koordinatfel (>200 m)" filtrerar till bara de med fel

**Framtida utbyggnad av KBR-lagret**

KBR-byggnader med `kyrka=true` kan ha `nuvarandeAnvandning` som inte är
aktiv gudstjänstkyrka - t.ex. "Kyrka - ej i bruk" eller "Kapell". Och
byggnader med `kyrka=false` (församlingshem, klockstaplar, pastorsexpeditioner)
finns i KBR men matchas inte alls idag.

Konkret observerat fall: *Nora församlingsgård* (KBR id 37159) har
`kyrka=true` och `nuvarandeAnvandning: "Kyrka - gudstjänstkyrka"` men
heter inte "kyrka" och matchar inte OSM-noden (som också heter
"Nora församlingsgård" men saknar `amenity=place_of_worship`). Det är
alltså ett legitimt kbr_only-fynd - byggnaden används som kyrka vintertid
men är otaggad i OSM.

Möjliga förbättringar:
- Använd `nuvarandeAnvandning` och `nuvarandeFunktion` för att dela upp
  kbr_only i underkategorier: aktiv kyrka, ej i bruk, kapell.
- Hämta `kyrka=false`-byggnader som ett separat lager (församlingshem,
  klockstaplar m.m.) för att ge en komplett bild av Svenska kyrkans
  byggnadsbestånd.
- Matcha mot bredare OSM-taggar (t.ex. `building=church` utan
  `amenity=place_of_worship`) för att fånga noder som Nora församlingsgård.

Popup för berikade features utökas med:
- "KBR: X m från OSM" (primärt)
- "KBR: Y m från Platser" (sekundärt)

**4. Workflow + rebuild.sh**

`osm-deploy.yml`: lägg till `build_kbr.py`-steg före `build_diff.py`.
`rebuild.sh`: lägg till `uv run build_kbr.py`-rad.
`serve.py` rebuild-endpoint: lägg till KBR-steg i live-rebuild-flödet.

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
egna kyrksymboler och färger. Nybyggda kyrkor visas med full mättnad och
tonas successivt ned till 20% vid 400+ års ålder, vilket gör det lätt att
se var nya kyrkor byggs. Nyare kyrkor visas ovanpå äldre i z-led.

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

- **Koordinatfellista** - implementerad som `kbr-kvalitet/`, se nedan.

- **Stift-filter** - dropdown för att filtrera på ett stift.

- **Mobilens adressfält täcker UI:t** - delar av sidan täcks av webbläsarens
  adressfält/navigeringsfält på mobil. Troligen ett `100vh`-problem: mobila
  webbläsare räknar `100vh` som hela skärmhöjden exklusive UI-krom, men
  adressfältet kan dyka upp ovanpå innehållet. Fix: använd `100dvh`
  (dynamic viewport height, stöds i moderna mobilwebbläsare) med `100vh`
  som fallback, och/eller `env(safe-area-inset-bottom)` för iOS.
  Kontrollera att kartan och slidern inte hamnar bakom UI-krom.

### 8. KBR-kvalitetsrapport (`kbr-kvalitet/`) ✅ Funktionell

Datakvalitetsverktyg som hämtar ~3 500 kyrkor från KBR och jämför mot
SVK Platser-API:t och OSM. Körs lokalt med `APIKEY_PROD=... uv run
kbr-kvalitet/build_report.py` (~3 min inkl. Overpass-hämtning).

**Kontrollerar:**

- Koordinatavvikelser KBR vs Platser och OSM (matchning: namn +
  geografiskt närmaste kandidat, cap 200 km)
- Datumkvalitet: omöjlig ordning, lång byggnadstid (>300 år), saknade datum
- Koordinatkvalitet: utanför Sverige, rundade koordinater (1 km precision),
  duplikatkoordinater
- Namnkvalitet: duplikatnamn inom stift
- Status: "Kyrkan används inte", fundamentala funktionsändringar (kyrka/icke-kyrka)
- Komplettering: saknade RAA-id, byggarea, fastighetsbeteckning, planform,
  material, tillgänglighetshandlingsprogram
- Förvaltning: poster ej uppdaterade sedan 2020, ägar/geo-enhet mismatch

**Resultat (2026-05-02):** 38 kyrkor inaktiva, 64 funktionsändrade, 324
saknar RAA-id, 2 011 saknar planform, 1 960 saknar tillgänglighetshandlingsprogram,
84 koordinatavvikelser >= 200 m mot Platser/OSM.

**Output:** `data/report.csv` (koordinatavvikelser), `data/quality.json`
(alla fynd), ⌖-knappar i alla tabeller hoppar till KBR-koordinaten på karta,
"Skriv ut / PDF" exporterar samtliga tabeller.

**Återstår:**

- Lämna `report.csv` till kyrkobyggnadsavdelningen för åtgärd.
- Ev. komplettera med UnitAPI-validering av `agandeEnhetLkf`-koder.
- **K-samsök/RAÄ som fjärde koordinatkälla** - se nedan.

### 8b. KBR vs K-samsök koordinatjämförelse (ej påbörjad)

Stickprov 2026-05-02 bekräftade att K-samsök/BBR har oberoende koordinater
och identifierar samma fel som Platser+OSM. Linköpings domkyrka: KBR avviker
11 293 m mot RAÄ/BBR - RAÄ stämmer med Platser och OSM.

**Varför det är intressant:** KBR-koordinater registreras av kyrkan själv.
RAÄ/BBR är en oberoende källa. Avvikelse bekräftad från tre oberoende håll
är starkare bevis för ett KBR-fel än avvikelse mot bara en källa.

**Matchningsflöde (verifierat):**

1. KBR-fältet `fastighetsbeteckning` → K-samsök `cadastralUnit`-sökning
   `GET ksamsok/api?method=search&query=cadastralUnit="<fastighet>"&fields=itemId`
2. Svar ger `http://kulturarvsdata.se/raa/bbr/<id>` → hämta som RDF
3. RDF-dokumentet listar länkade `raa/bbrb/<id>`-poster (byggnadsdelen)
4. Hämta `raa/bbrb/<id>` som RDF → extrahera `<gml:coordinates>lng,lat</gml:coordinates>`

Koordinaterna är WGS84 (EPSG:4326), direkt jämförbara med KBR efter pyproj-konvertering.

**Begränsningar:**

- Tre HTTP-anrop per kyrka → ~10 500 anrop totalt, ~30 min med rimlig throttling
- 14 KBR-kyrkor saknar `fastighetsbeteckning` - de kan inte matchas
- Inte alla BBR-poster har koordinater i `bbrb`-undernivån
- K-samsök och KBR kan ha gemensam ursprungskälla för nyare kyrkor,
  men RAÄ mäter/verifierar oberoende för kulturminnesmärkta objekt

**Implementation i `build_report.py`:**

Lägg till ett nytt pass efter KBR-hämtningen som batchar K-samsök-lookups
för de kyrkor som redan avviker mot Platser/OSM (ca 84 st med >200 m).
Spara `raa_lat`, `raa_lng`, `avstand_raa_m` i `report.json`.
Visa RAÄ-markör (lila?) på kartan i koordinatavvikelse-fliken.

### 6. Kalenderhändelse-aggregator (`calendar-aggregator/`)

Hämta events från [CalendarAPI](#CALENDARAPI) för flera enheter och
visa som en gemensam stiftskalender eller liknande. Bra övning på
OAuth2-flödet och OData-aktig sökning.

### 9. KBR + Riksantikvarieämbetet K-samsök (`kbr-raa/`)

KBR har ett `identitetRAA`-fält per kyrka som är en direktlänk till RAÄ:s
kulturmiljöregister. K-samsök (SOCH) har ett öppet REST/SPARQL-API:
`https://kulturarvsdata.se/ksamsok/api`.

Möjliga vinklar:
- Berika `kbr-tidslinje/` med skyddsstatus per kyrka (byggnadsminne,
  kyrkligt kulturminne, skyddsklass K1/K2/K3) - visas i popup.
- Komplettera `kbr-kvalitet/` med en flik "RAÄ-koppling": kyrkor vars
  `identitetRAA` inte hittas i K-samsök, eller vars koordinater avviker.
- 324 kyrkor i KBR saknar `identitetRAA` - K-samsök-sökning på namn +
  koordinat kan hitta troliga matchningar.

Öppet API, ingen nyckel krävs. Enda externa beroendet är pyproj (redan
installerat i projektet).

### 10. kbr-tidslinje + historiska kartlager (`kbr-tidslinje/`, utbyggnad)

Lantmäteriet har ett öppet WMS med historiska kartor:
- Häradskartan (~1870-1900): `https://api.lantmateriet.se/historiska-ortofoton/...`
- Ekonomiska kartan (1930-1980)
- Fältkartan / Generalstabskartan (1800-tal)

Tile-lagret byts automatiskt baserat på slider-år, så år 1880 visar
Häradskartan, år 1950 Ekonomiska kartan osv. Tekniskt: byt `L.tileLayer`-URL
när `currentYear` passerar en tröskeln. Kräver att man identifierar rätt
WMS-endpoint och lager-namn - se Lantmäteriets API-portal.

Visuellt stark funktion: bygger på befintlig kbr-tidslinje utan ny datapipeline.

### 11. signage-platser + SMHI väderprognos (utbyggnad)

SMHI har ett helt öppet prognos-API (ingen nyckel):
`https://opendata-download-metfcst.smhi.se/api/category/pmp3g/version/2/geotype/point/lon/{lng}/lat/{lat}/data.json`

Utbyggnad av `signage-platser/`: lägg till en väderrad i displayen baserat
på platsens koordinater. Hämtas direkt från SMHI vid varje polling-cykel.
Relevant för utomhusarrangemang och kyrkbesökare.

Begränsningar: SMHI-prognosen täcker bara Sverige och max ~10 dygn framåt.
Koordinater tas från Platser-API:ts `location`-fält.

### 12. Församlingsgränser + SCB befolkningsstatistik (`forsamling-befolkning/`)

SCB publicerar befolkningsdata på DeSO-rutor (250 m upplösning) som öppen
nedladdning: `https://www.scb.se/hitta-statistik/statistik-efter-amne/befolkning/`.

Kombinera med församlingsgränserna från `forsamlingskarta-leaflet/`:
- Räkna antal SCB-invånare per församling via spatial join (pyproj/shapely)
- Koropletlager i Leaflet: färg per befolkningstäthet
- Popup: "X invånare, Y km², Z inv/km²"

Intressant kontrast storstads- kontra glesbygdsförsamlingar. Kräver
nedladdning av SCB-fil (shapefile/GeoJSON) och en enkel Python-join mot
KML/GeoJSON från Församlingskartor-API:t.

### 13. KBR + Mapillary-fasadfoton (`kbr-tidslinje/`, utbyggnad)

Mapillary har ett gratis API (kräver API-nyckel, gratis registrering):
`https://graph.mapillary.com/images?fields=id,thumb_256_url&bbox={west},{south},{east},{north}`

Hämta närmaste gatufoto inom 100 m från KBR-koordinaten och visa som
miniatyr i popup. Enklaste berikandet av kbr-tidslinje - ett klick
öppnar full bild på mapillary.com om täckning finns.

Genomförbarhet beror på Mapillary-täckning utanför städer - många landsbygdskyrkor
kan sakna foton. Räkna andelen täckta som ett kvalitetsmått.

## Generellt - nästa steg per API

Status efter verifiering med vår nyckel mot test 2026-05-01:

| API | Status | Nästa steg |
|---|---|---|
| CalendarAPI | (saknar Azure-nyckel) | Skaffa Azure APIM subscription-key. |
| CHURCHCALENDAR | ✓ funkar publikt | Lågt hängande - bygg `kyrkoaret-widget/`. |
| Enhetsinformation | ✗ 302 mot test | Prenumerera på "Enhetsinformation" via portalen. |
| Församlingskartor | ✓ ingen auth | Validera lager-listan via `GetCapabilities`. |
| Församlingssök | ✗ 401 CallerInvalid | Prenumerera på "Församlingssök" på portalen. |
| KBR | ✓ prod | Används i `kbr-tidslinje/` och `kbr-kvalitet/`. Koordinater i SWEREF99TM. |
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
