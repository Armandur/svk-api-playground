# Utlåtande: rebuild.md

Genomgång av designdokumentet efter att jag läst `build_report.py` (745
rader), relevanta delar av `index.html` (900 rader), `README.md`, samt
modulerna `KBR.md`, `UNITAPI.md`, `ENHETSINFORMATION.md` och `PLATSER.md`.

> **Not:** Första versionen av detta utlåtande skrevs enbart från
> `rebuild.md` utan att läsa kod. Flera påståenden där visade sig vara
> fel när jag läste koden (markerade nedan med "korrigering"). Detta är
> en omarbetad version.

---

## Övergripande intryck

Dokumentet är välresonerat på riktningen men har **två blinda fläckar**:

1. Det missar att UI:t redan hanterar `bv_lat/bv_lng` som separata fält
   för Kyrka/kapell. Kritiken om saknad `primary_source` gäller bara en
   smal delmängd (BV-only-typerna) och kan lösas billigare än föreslaget.
2. Det missar att kvalitetsanalysen är **inkläst i KBR-fetch-loopen**
   (rad 162-262 i `build_report.py`). All cache-arkitektur måste lyfta
   ut den, annars cachar man rådata medan kvalitetslistorna fortfarande
   beräknas vid varje körning - vilket ändå tvingar en full omläsning.

ID-mappning via LKF är fortfarande den största icke-utredda frågan, men
mer nyanserad än jag först trodde (se nedan).

---

## Faktarättelser från min första läsning

### "primary_source saknas" - delvis fel

Jag tog rebuild.md:s ord för det att UI:t saknar primärkällans markering.
**Fel.** I `index.html` (rad 461-509) finns redan:

- Separat lila prick för BV (`#7B1FA2`/`#CE93D8`) på `bv_lat,bv_lng`
- Separat röd KBR-prick på `kbr_lat,kbr_lng`
- Separat blå Platser-prick och grön OSM-prick
- Polylines mellan KBR och varje annan källa

För **Kyrka/kapell** med BV-data finns alltså redan separation. BV
joinas dessutom på klientsidan i `index.html` (rad 822-827) via
`kbr_id` mot `/api/bv`-endpointen.

Den **äkta** primary_source-frågan gäller bara BV-only-typerna
(Församlingshem, Administrationsbyggnad, Krematorium, Klockstapel). I
`build_report.py` (rad 568-622) sätts:

```python
row = {"namn": bv["namn"], ..., "kbr_lat": bv["bv_lat"],
       "kbr_lng": bv["bv_lng"], "kbr_id": None, "typ": "Församlingshem"}
```

Här är `kbr_lat/kbr_lng` egentligen BV-koordinater och `kbr_id: None`.
**`kbr_id == null` är redan signalen** att raden inte är KBR-baserad.
UI:t behöver bara kolla det istället för att lägga till ett nytt fält.

**Reviderad rekommendation:** lägg inte till `primary_source`. Använd
`kbr_id == null` som signal i UI:t och färga primärpricken lila (BV) i
det fallet, röd (KBR) annars. Mindre nytt API-yta, samma effekt.

### "ID-baserad matchning" - vägen finns, men ger bara enhets-skopning

Jag rekommenderade en utredning av LKF-mappning som steg 0. Det är
fortfarande rätt - men vad mappningen GER är mer begränsat än
rebuild.md antyder:

- KBR har `agandeEnhetLkf` och `geografiskEnhetLkf` (LKF-koder).
- UnitAPI har `lkf` och `unitId`.
- Platser har `owner.id` som **är** `unitId` enligt `PLATSER.md`.
- KBR har också `facilityPartId` (UUID), men `KBR.md` säger uttryckligen
  att den **inte matchar Platser-API v4**.

Vägen `KBR.agandeEnhetLkf → UnitAPI.unitId → Platser.owner.id` ger alltså
**enhets-nivå** matchning ("dessa platser ägs av samma församling som
denna byggnad") - inte byggnads-nivå. En församling har typiskt 1-5
kyrkor + församlingshem + kansli, så den minskar kandidatmängden men
eliminerar inte närmaste-grann-steget.

Det är fortfarande värt att göra: när nuvarande namnmatchning hittar
flera kyrkor med samma namn över hela landet (Mariakyrkan, Sankt
Olof, ...) blir LKF-skopning **mycket** starkare än en avståndscap på
200 km.

**Reviderad rekommendation:** behåll steg 0 (LKF-utredning) men förvänta
ID-mappning som **filter**, inte som direktjoin. Implementationsmodell:
matcha namn först, om flera kandidater - filtrera på `owner.id` =
mappad `unitId` från `agandeEnhetLkf`. Om en kvar, klar. Annars välj
närmaste.

### "Monolitisk pipeline utan caching" - korrekt, men cache-arkitekturen kompliceras

Korrekt observation. Men det rebuild.md missar är att kvalitetsanalysen
sker **inuti** KBR-fetch-loopen (rad 162-262):

- 14 olika `q_*`-listor byggs upp under iterationen
- Logiken läser fält som `nybyggnadFran`, `invigning`, `materialStomme`,
  `andradDatum` osv. ur varje batch
- Inget separat post-process-steg

För att cacha rådata måste man:
1. Bygga om så att fetch bara skriver `data/raw/kbr_churches.json`.
2. Flytta all q_*-logik till en separat `analyze_quality()` som läser
   den filen.

Det är **inte** en parallellt självklar refaktorering - kvalitetslistorna
binder mot råa fält, inte mot den slimmade `kbr_churches`-strukturen som
matas vidare till matchningen. Säkerligen genomförbart, men dyrare än
"separera fetch från match".

**Reviderad rekommendation:** behåll min förenkling till en `build.py`,
men erkänn att fetch/analyze-uppdelningen kräver två loopar över
rådata - en som extraherar matching-fält, en som extraherar
kvalitetsfält. Antingen kör båda på samma cachade fil, eller cacha
rådata oserialiserad och låt båda läsarna göra sitt jobb.

---

## Vad rebuild.md helt missar

### `report.csv` är ett operativt artefakt

`build_report.py` skriver `data/report.csv` med alla rader
`avstand_m >= 200m`. Enligt `README.md` rad 43: "för rapportering till
kyrkokansliet". Det betyder att kolumnsetet i CSVen (rad 736-739 i
build_report.py) är ett **publikt kontrakt** med en extern mottagare,
inte ett internt format.

Vid refaktorering: ändra inte CSV-strukturen utan att samordna med
mottagaren. Lägg gärna till kolumner, men ta inte bort eller döp om
existerande.

Det här är värt att flagga eftersom rebuild.md föreslår "primary_source
i build_report.py" - om det landar i CSVen är det en extern ändring,
inte bara intern.

### Krematorium matchas mot kyrkogårdar (potentiell bugg)

I `build_report.py` rad 472-475:

```python
is_cemetery = (tags.get("landuse") == "cemetery"
               or tags.get("amenity") in ("grave_yard", "crematorium"))
```

`crematorium` klassas som `osm_typ="begravningsplats"`. Sedan på rad
593-604 matchas BV-Krematorium mot `osm_cemetery_by_name`. Det
fungerar **bara om** OSM-objektet har samma namn som BV-krematoriet,
men en kyrkogård vid samma namn kan plockas upp först (närmaste-grann).

**Rekommendation:** skapa egen `osm_typ="krematorium"` och matcha BV
mot den. Litet ändring, eliminerar en konkret felträffsklass.

### `platser_extra.json` är rådata som inte fullt utnyttjas

`build_report.py` skriver `platser_extra.json` med rådata för
parishhome/cemetery/secretariat. UI:t läser den för
BV-jämförelseflikens lager och för att matcha BV mot Platser.

Värt att tänka på: detta är en de-facto cache av Platser API:t med
rätt typer, redan strukturerad. Om man **ändå** ska bygga om till
caching - använd den som kärnformat.

### BV-flikens jämförelse är klientside

`index.html` rad 658-708 gör BV vs KBR-jämförelsen helt på klientsidan
genom `hvs()`-haversine. Det betyder att tröskelvärdet för "avvikelse"
kan ändras utan att build_report.py körs om.

Det är ett **medvetet val** (eller åtminstone en bra biverkning): BV-
matchningen kostar inget vid build, alla iterationer på tröskeln sker
i webbläsaren. Tar man bort det till serversidan förlorar man den
flexibiliteten.

**Rekommendation:** behåll klientside-join för BV. Cache BV-CSVen som
JSON istället, för enklare frontend-läsning.

---

## Reviderad prioriteringstabell

| Prio | Ändring | Motivering |
|------|---------|-----------|
| 0 | Utred LKF -> unitId -> owner.id-mappning. Förvänta enhetsnivå-filter, inte direktjoin | Eliminerar kors-landsmatcher utan att blåsa upp kandidaterna |
| Hög | Kolla `kbr_id == null` i UI för BV-only-typer, färga lila (BV) i stället för röd (KBR) | Ersätter `primary_source`-förslaget, billigare |
| Hög | Egen `osm_typ="krematorium"` i build_report.py | Konkret felträffsklass i nuvarande kod |
| Hög | Dela upp index.html (CSS + utils + map + bv-flik + quality-flik) | 900 rader blockerar all framtida UI-iteration; även små buggar (`hb` dubbelt) syns |
| Medium | Snapshot av report.json + quality.json per dag (utan UI) | Billigt nu, omöjligt att rekonstruera retroaktivt |
| Medium | Tester för `normalize`, `closest_match`, `haversine` | Frikoppla från fetch innan resten refaktoreras |
| Medium | Cache rådata + analyze-steg, en `build.py` med `--skip-fetch` | Erkänn att q_*-logiken behöver lyftas ur KBR-loopen |
| Medium | Färskhetscheck + JSON-format för BV (ersätt CSV-läsning) | Underlättar klientside-konsumtion |
| Låg | Koordinatprecisions-rapport för KBR/Platser | Oförändrad |
| Låg | OSM `community_centre` för Församlingshem | Eventuellt onödig efter LKF-skopning |

---

## Bevara

Saker som rebuild.md inte nämner men som inte ska röras vid en refaktor:

- **`report.csv`-formatet** - externt kontrakt mot kyrkokansliet.
- **`kbr_id` som primärnyckel** mellan output-filer - används för
  klientside-join, byt inte ut.
- **Klientside BV-jämförelse i UI** - tillåter tröskeljustering utan
  rebuild.
- **`/api/bv`-endpointen i serve.py** - billig dynamisk koppling till
  CSV som uppdateras manuellt.
- **Sex flikar i UI:t** (Koordinatavvikelser, Datumkvalitet,
  Koordinatkvalitet, Namnkvalitet, Status & avyttring, Komplettering).
  README beskriver dem; behåll struktur vid uppdelning.

---

---

## UI/UX-förbättringar

`rebuild.md` adresserar arkitektur men inte användarupplevelsen. Här
är en separat lista konkret förslag på UI/UX-nivå, baserade på
genomläsning av `index.html`. Sorterade efter värde/insats.

### Hög effekt, låg insats

#### 1. Visa sortering tydligt i tabellerna

Alla `<th data-col>` är klickbara (rad 475-478) men UI:t signalerar
inte att kolumnen är sorterbar och åt vilket håll. Användaren
upptäcker funktionen av en slump.

**Fix:** lägg på pil (▲/▼) i `<th>` på den sorterade kolumnen,
en svag färg (`cursor:pointer; color:#fff8`) på övriga sorterbara
kolumner. Två rader CSS + en rad i sortlyssnaren.

#### 2. "Rensa filter"-knapp i filter-panelen

Idag måste man manuellt klicka av varje kryssruta i Stift/Typ/Källa
för att nollställa. För 14 stift är det 14 klick.

**Fix:** lägg till en sticky-knapp "Rensa alla" i `#filter-panel`
(rad 159-170). En rad HTML + en handler som tömmer `filterStift`,
`filterTyp`, återställer `filterSrc` och kör `applyFilter()`.

#### 3. "Välj alla / Inverter"-genväg i multiselect

Samma problem som ovan: inget snabbt sätt att t.ex. se "alla utom
Lunds stift". 

**Fix:** två små länkar ("Alla", "Inverter") över Stift- och
Typ-listorna. Småändring som markant förbättrar workflow.

#### 4. Sökruta i sidofältslistan på koordinatfliken

900-radersfilen visar avvikelselistan men har ingen sökruta. Vill
man hitta "Härnösand" får man scrolla eller använda Ctrl+F (som
fungerar men inte koordinerat med kartan).

**Fix:** `<input placeholder="Sök kyrka...">` ovanför sidebar-tabellen
som filtrerar på namn-substring. ~10 rader kod.

#### 5. Mobil: tooltips ersätts av click-popups på markörer

`bindTooltip(..., {sticky:true})` (rad 511) fungerar bara på hover.
På touch-skärmar visas tooltipen aldrig - användaren ser bara
färgade prickar utan info.

**Fix:** `bindPopup` istället för (eller utöver) `bindTooltip` -
Leaflet öppnar popup på click oavsett device. Liten ändring per
markör-anrop, gör mobilversionen användbar.

#### 6. Klickbara stat-counters

`<span id="cnt-5k">` (rad 153-156) visar antal avvikelser i varje
bucket men är inte klickbara. Användaren kan inte snabbt hoppa till
"visa bara >=1km".

**Fix:** gör dem till `<button>` som sätter `threshold` till 5000 /
1000 / 200. Tre handlers, ingen ny CSS behövs.

#### 7. Print-CSS visar inte avvikelse-sidofältet

`@media print` (rad 109-120) döljer hela `#tab-koordinater` när man
skriver ut. Det betyder att exporten missar avvikelse-listan
helt - bara kvalitetsflikarna kommer med.

**Fix:** antingen rendera avvikelselistan separat i print-vyn (som
en egen sektion) eller dokumentera tydligt att utskriften bara
täcker kvalitetsflikarna. Idag är beteendet förvirrande.

### Medium effekt, medium insats

#### 8. Sortering på kvalitetstabellerna

Datumkvalitet, Komplettering osv har inga klickbara `<th>` alls.
Användaren kan inte sortera "RAA saknas" på invigningsår för att
se gamla kyrkor först.

**Fix:** generisk sorteringsfunktion delad med koordinatfliken
(när index.html ändå delas upp - se huvudutlåtandet).

#### 9. Sökruta på alla kvalitetsflikar

Samma princip som punkt 4 men mer värdefullt här - vissa listor
har 1000+ rader (t.ex. `material_saknas`, `byggarea_saknas`) och
är ohanterliga utan sök.

**Fix:** en gemensam `q-section-search` ovanför varje tabell
(eller en global "filter all tables on this tab"-input).

#### 10. Intern navigering på Komplettering-fliken

`#tab-komplettering` har **9 stackade sektioner** (RAA saknas,
Byggarea, Fastighet, Planform, Material, Handlingsprogram,
Inte tillgänglighetsanpassad, Senast ändrad, Ägare-mismatch).
Användaren scrollar långt.

**Fix:** sticky innehållsförteckning (chip-länkar) överst i
`.quality-pane` som hoppar till respektive sektion. Eller dela
fliken i två: "Komplettering" och "Förvaltning".

#### 11. URL-state för delbara länkar

Idag tappar man tillstånd vid sidladdning. En delad länk till
"avvikelser >=1km, Lunds stift, BV-källa" är inte möjlig.

**Fix:** persistera `threshold`, `filterStift`, `filterTyp`,
`filterSrc`, aktiv flik i `location.hash`. Läs vid laddning.
Standardimplementation, ~30 rader.

Bonus: `#kbr=32555` öppnar specifik kyrka direkt (zoomar +
expanderar).

#### 12. Loading-state under datafetchen

`fetch('data/report.json')` (rad 779), `kbr_all.json` (rad 811),
`/api/bv` (rad 819), `quality.json` (rad 838), `stats.json` (rad
891) körs sekventiellt/parallellt utan progress-indikator.

`<div id="no-data">Laddar data...</div>` står tomt under tiden.

**Fix:** skeleton-rader i sidebar och kvalitetstabeller medan data
laddar. Eller en spinner med text som uppdateras ("Laddar
KBR...", "Laddar Platser...").

### Medium effekt, högre insats

#### 13. Kluster av markörer vid utzoomad vy

Vid zoom-nivå 5-7 (hela Sverige) visas alla matchade rader som
överlappande prickar. Mönster syns inte. Kartan blir grötig vid
1000+ avvikelser.

**Fix:** Leaflet.markercluster (en CDN-länk + ändringar i
`buildMarkers`). Vid utzoomning grupperas markörer i kluster med
antalsbadge. Kluster färgas efter värsta avvikelsen i klustret.

Standard tillägg, men kräver att man tänker igenom logiken: vill
man klustra alla källor (KBR + Platser + OSM + BV) eller bara
KBR-prickarna och visa övriga som linjer?

#### 14. Logaritmisk threshold-slider

`<input type="range" min="0" max="50000" step="100">` (rad 148)
ger 500 steg, men 90% av användningsfallen ligger under 1000.
Slidern är otrymlig på låga värden.

**Fix:** logaritmisk mappning - reglaget går 0-100, värdet
beräknas `Math.round(Math.exp(reglage / 12) - 1)`. Eller
diskreta steg: 0, 50, 100, 200, 500, 1000, 2000, 5000, 10000,
50000.

#### 15. Färgkod / ikon för byggnadstyp i sidofältet

Sidofältets lista (rad 460-465) visar Avvikelse, Kyrka, Stift.
Typ (Kyrka/kapell, Begravningsplats, Församlingshem etc.) syns
först i expanderad detalj. När man har blandade typer i listan är
det svårt att skanna.

**Fix:** liten färgad badge eller emoji-ikon framför kyrknamnet:
🏛 Kyrka, ⚰ Begravningsplats, 🏠 Församlingshem, 🏢 Kansli, 🔥
Krematorium, 🔔 Klockstapel. Eller bara en `<span>` med stiftspecifik
bakgrundsfärg.

(Dock: användarens preferens är "inga emojis" - så håll det till
färgade prickar.)

#### 16. Exportera filtrerad data

`report.csv` på filsystemet är hårdkodat tröskel 200m. Vill man
ha "alla >=1km i Lunds stift" finns ingen export.

**Fix:** "Exportera CSV"-knapp i `#coord-controls` som tar
nuvarande filtrerade `rs` och kör `Blob → download`. ~20 rader.

### Snyggrättningar

#### 17. KML-skyddad-flagga i listvy

`r.skydd` exponeras bara i den expanderade detaljraden (rad 471).
KML-skyddade kyrkor är högintressanta - markera dem direkt i
listan (en liten 🛡 eller en `<sup>K</sup>`-badge).

#### 18. Kvalitetsbadge: visa siffran tydligare

`q-badge` (rad 76-78) är 10px font, väldigt diskret. Användaren
missar kontrasten "0 problem" (grön) vs "47 problem" (röd) eftersom
båda är samma småskala.

**Fix:** öka font till 12px, padding till 2-8px. Två rader CSS.

#### 19. Inkonsistent `q-badge.ok`-tilldelning

`setCount(id, n, warn)` (rad 440) ger grön bara om `warn=true && n=0`.
För kvalitetsfält där `warn=false` (t.ex. duplikatnamn, byggarea
saknas) blir badgen alltid röd även när det är 0. Det signalerar
"problem!" där det inte finns problem.

**Fix:** ändra till `el.className = (n === 0) ? 'q-badge ok'
: 'q-badge'`. Tre tecken.

#### 20. Variabeldubblett `hb` (rad 461)

```js
const hp = r.avstand_platser_m != null,
      ho = r.avstand_osm_m != null,
      hb = r.bv_lat != null;
```

Ser fint ut - jag flaggade fel i tidigare utlåtande att `hb` var
deklarerad dubbelt. Bortse från den punkten i mitt huvudutlåtande.

### Vad jag INTE rekommenderar

- **Stift som markörfärg** - kartan har redan färg per källa och
  per avvikelseintervall. Tre färgaxlar gör den oläsbar.
- **Heatmap över Sverige** - användarna är redan "visa konkreta
  avvikelser", inte "vart är problemen koncentrerade". Heatmap är
  cool men ger inte mer än kluster.
- **Helsidofliken med dashboard** - verktyget är operativt
  ("granska och rapportera"), inte beslutsstödjande. En dashboard
  med "kvalitetsindex per stift" vore demos-feature, inte
  arbetsverktyg.
- **Realtidsuppdatering** - data uppdateras manuellt via build-
  skript. Live-sync är off-scope.

---

## Sammanfattning

Rebuild.md har rätt riktning men fel detaljer på två punkter:

1. **`primary_source`-förslaget är överkurs** - `kbr_id == null` är
   redan signalen, byt färg i UI istället.
2. **Cache-arkitekturen är inte trivial** - kvalitetsanalysen är
   inkläst i fetchen och måste lyftas ut först.

Tre konkreta tillägg som rebuild.md missade:

1. **Krematorium felmatchas mot kyrkogårdar** i nuvarande OSM-typning.
2. **`report.csv` är ett externt kontrakt** med kyrkokansliet och får
   inte brytas tyst vid refaktor.
3. **Klientside BV-jämförelse är medveten flexibilitet** - bevara den.

Min ursprungliga rekommendation att lyfta LKF-utredningen till steg 0
står kvar, men förväntningen behöver justeras: ID-mappningen är ett
**filter** för namn-matchning, inte en direktjoin. Det är ändå värt
mödan eftersom det adresserar nuvarande algoritmens svagaste fall
(samma kyrknamn över hela landet).

---

## Reaktion på rebuild-gemini.md

Läst Geminis utlåtande (59 rader). Det är en **vision-pitch för
fullständig rewrite på separat branch**, mer abstrakt än konkret. Jag
håller delvis med och delvis inte. Sammanfattning först, detaljer sen.

### Var vi är överens

- Separation av Fetch / Match / Quality / UI är rätt riktning.
- Caching med TTL per källa.
- index.html ska delas upp i ES-moduler (vanilla JS, ingen bundler).
- URL-hash som state-mekanism (Gemini gör det centralt, jag hade som
  punkt 11 i UI/UX-listan - hans placering är bättre).
- **Krematorium ska vara egen typ med egen OSM-matchning** (Gemini
  pekar ut samma bug jag flaggade).
- Klientside CSV-export från rikt JSON.

### Var jag är oense

#### 1. "Fullständig rewrite" är fel verktyg

Geminis huvudtes - "fullständig rewrite på separat branch" - är dyrt
och riskabelt här. Tre invändningar:

- **Verktyget är operativt.** `report.csv` skickas till kyrkokansliet
  (per `README.md` rad 43). En rewrite-branch som tar veckor betyder
  att gamla verktyget måste underhållas parallellt, eller att rewriten
  måste vara klar i ett svep utan att bryta CSV-formatet. Gemini
  adresserar inte detta alls.
- **Lekplats-projekt med begränsad tidsbudget.** Geminis 5-stegs plan
  (skeleton, caching-lager, LKF-bryggning, UI-migration, quality-port
  av 20+ tester) är veckor av arbete. Risken är att rewriten aldrig
  blir klar och både gammal kod och halvfärdig ny kod lever sida vid
  sida.
- **Inkrementellt fungerar.** Min prioriteringstabell ger samma
  riktning men i steg som var och en kan committas och verifieras.
  Steg 0 (LKF-utredning) tar en eftermiddag och avgör om de stora
  stegen ens behövs.

**Reaktion:** ja till en `rebuild`-branch som arbetsplats, nej till
"big-bang rewrite". Använd branchen för en serie commits där varje
ändring är test- och rollback-bar.

#### 2. "LKF-first matchning, obligatoriskt" - tekniskt fel

Geminis matchnings-pipeline:

> 1. Strikt ID-matchning (via LKF/EnhetsID).
> 2. Namn-matchning inom samma stift/enhet.
> 3. Geografisk fallback.

Steg 1 är **fel**. Det finns inget 1:1-ID mellan en KBR-byggnad och en
Platser-plats. `KBR.md` säger uttryckligen att `facilityPartId`
**inte** matchar Platser-API v4. LKF/`unitId` ger bara
**enhets-skopning** (alla platser som ägs av samma församling som
denna byggnad) - en församling har typiskt 1-5 kyrkor + flera andra
byggnader, så LKF kan inte ensam identifiera en byggnad.

Geminis "obligatoriskt LKF, annars Low Confidence" missar det här.
Korrekt formulering är: **namn-match först, LKF som filter när det
finns flera kandidater**. Det är det jag rekommenderade i steg 0.

#### 3. "Skippa report.csv som standard" - missar externt kontrakt

Gemini föreslår att slopa CSV-output och generera den on-the-fly i
webbläsaren. Det missar att CSV:n är ett **avtalat format** med
kyrkokansliet (mottagare av rapporten). Att flytta det till
"webbläsaren genererar vid behov" är inte en designfråga utan en
process-fråga: kyrkokansliet får inte längre filen via batch.

**Reaktion:** behåll CSV-genereringen i build-skriptet. Lägg till
klientside-export som komplement, inte ersättning.

#### 4. "primary_source genomgående" - överkurs

Gemini anammar `rebuild.md`:s ursprungliga förslag. Jag argumenterade
emot det i punkt "primary_source saknas - delvis fel" ovan: UI:t har
redan separata fält per källa, och `kbr_id == null` signalerar
BV-only. Att lägga till `primary_source` är new API surface utan ny
funktionalitet.

#### 5. Gemini missar viktiga saker jag flaggat

- **q_*-logiken är inkläst i fetch-loopen** (rad 162-262 i
  build_report.py). Geminis "kvalitets-plugins" är ett bra mål, men
  vägen dit är icke-trivial. Att säga "Quality-port: portfölj över de
  20+ testerna" som steg 5 underskattar arbetet.
- **Inga tester nämns**. Refaktorering utan tester är riskabelt - hur
  vet man att match-logiken efter rewriten ger samma resultat?
- **Snapshot/historik** - inget om att börja samla retroaktivt-
  omöjlig-data.
- **UI/UX-detaljerna** - Gemini sätter ramen ("modulär frontend") men
  inget om de 20 konkreta UX-problem jag identifierade
  (sortering inte synlig, filter saknar Rensa, hover-tooltips bryter
  mobil, print-CSS missar avvikelse-listan, etc.).
- **`feature/rewrite`** som branch-namn bryter projektets svenska
  konvention.

### Vad Gemini bidrar som jag missat

- **"Quality-plugin"-formatet** - jag sa "lyft ut q_*-logiken" utan
  konkret struktur. En `QualityCheck`-klass som returnerar
  standardiserade `Finding`-objekt är en bra abstraktion: nya
  kontroller kan deklareras utan att röra huvudloopen. Värt att
  designa in när man ändå rör koden.
- **`UnitMapper` som dedicerad komponent** - jag pratade om
  LKF-utredning som ett steg. Gemini gör det till en återanvändbar
  modul. Snyggare struktur.
- **URL-hash som central designprincip** - jag hade det som
  UI-tilläggspunkt. Att göra det till `state.js` med hela appens
  filter-state är arkitektoniskt renare.

### Sammanvägd rekommendation

Gör en `rebuild`-branch men använd den **inkrementellt**, inte för en
big-bang rewrite. Föreslagen ordning (kompromiss mellan mitt
utlåtande och Geminis):

1. **Steg 0 (1 eftermiddag):** Utred LKF -> unitId -> owner.id.
   Verifiera mot 20-30 kyrkor manuellt. Gå/inte-gå-beslut.
2. **Steg 1 (commit):** Krematorium som egen `osm_typ`. Liten
   isolerad fix, ger omedelbart värde.
3. **Steg 2 (commit):** Bryt ut CSS + utils.js + map.js från
   index.html. Ingen funktionsändring, möjliggör allt annat
   UI-arbete.
4. **Steg 3 (commit):** Tester för `normalize`, `closest_match`,
   `haversine`. Förutsättning för säker matchnings-refaktor.
5. **Steg 4 (commit):** Lyft ut q_*-logiken till `quality.py` med
   plugin-format (lånat från Gemini). Behåll output-format identiskt.
6. **Steg 5 (commit):** Cache rådata, separera fetch/analyze i
   build.py.
7. **Steg 6 (commit):** LKF-filter i match-logiken (om steg 0 gick).
8. **Steg 7+ (commits):** UI/UX-förbättringar från min lista.

CSV-formatet bevaras genom hela. Snapshot börjar samlas vid steg 5.
Branch:en kan mergas in i main efter varje steg om man vill - eller
hållas öppen tills hela kedjan är klar. Inget steg är "big bang".
