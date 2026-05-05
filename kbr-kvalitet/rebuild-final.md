# Byggdirektiv: kbr-kvalitet rebuild

Detta dokument är **byggunderlag** för Sonnet 4.6 (eller annan
implementatör) att genomföra rebuild av `kbr-kvalitet/`. Skrivet efter
diskussion mellan Rasmus, Opus 4.7 och Gemini.

Källor som konsoliderats: `rebuild.md` (Rasmus designöversyn),
`rebuild-opus.md` (Opus reaktion + UI/UX-analys),
`rebuild-gemini.md` (Geminis vision-pitch).

**Styrande principer:**

1. **Inkrementell, inte big-bang.** Varje steg är en commit som kan
   verifieras isolerat. Inga halvfärdiga tillstånd som lever länge.
2. **Bevara externa kontrakt.** `report.csv`-formatet, `kbr_id` som
   primärnyckel, sex flikar i UI:t.
3. **Verifierbarhet före elegans.** Tester för match-logiken innan
   den refaktoreras. Snapshot innan format byts.
4. **Inga onödiga abstraktioner.** Plugin-format för kvalitetstester
   när det betalar sig (steg 4), inte tidigare.

---

## Bakgrund och nuläge

### Vad verktyget gör

`kbr-kvalitet/build_report.py` (745 rader) hämtar fyra datakällor och
producerar JSON + CSV som `kbr-kvalitet/index.html` (900 rader)
visualiserar:

- **KBR API** - kyrkor (med datumkvalitet, koordinater i SWEREF99TM)
  och begravningsplatser
- **SVK Platser API** - churchAndChapel, parishHome, secretariat,
  cemetery
- **Overpass/OSM** - place_of_worship, cemetery, crematorium, campanile
- **BV CSV** (statisk fil) - Församlingshem, Administrationsbyggnad,
  Krematorium, Klockstapel

UI:t har sju flikar (efter senaste BV-tillägget):

1. Koordinatavvikelser (karta + sidebar med matchade rader)
2. Datumkvalitet
3. Koordinatkvalitet
4. Namnkvalitet
5. Status & avyttring
6. Komplettering & förvaltning (9 sektioner)
7. BV-jämförelse

Output:

- `data/report.json` - matchade rader (för karta + sidebar)
- `data/quality.json` - 14 kategoriserade kvalitetslistor
- `data/stats.json` - aggregerad statistik
- `data/kbr_all.json` - alla KBR-kyrkor (för "ej matchad"-lager)
- `data/kbr_begravningsplatser.json` - rådata för karta
- `data/platser_extra.json` - parishhome/cemetery/secretariat-rådata
- `data/report.csv` - **avvikelser ≥200m, externt kontrakt med
  kyrkokansliet**

### Identifierade problem

**Arkitektur:**

- Monolitisk pipeline utan caching: 5-15 min per körning, ingen
  möjlighet att uppdatera bara en källa.
- Kvalitetsanalysen (14 q_*-listor) är **inkläst i KBR-fetch-loopen**
  rad 162-262. Att separera fetch från analyze är icke-trivialt.
- Inga tester. Match-logiken (`normalize`, `closest_match`,
  `haversine`) är central men oprövad.
- 745 + 900 rader är över projektets riktlinje (400-500).

**Matchningskvalitet:**

- Namnmatchning + närmaste-grann är enda strategin. Generiska namn
  ("Församlingshem", "Mariakyrkan") ger felträffar.
- LKF-mappning från KBR till Platser via UnitAPI är inte utredd.
- Krematorium klassas som `osm_typ="begravningsplats"` (rad 472-478)
  och matchas mot kyrkogårdar.

**UI/UX:**

- Sortering finns men signaleras inte (klickbara `<th>` utan pilar).
- Filter-panel saknar "Rensa alla" och "Välj alla/Inverter".
- Hover-tooltips fungerar inte på touch.
- Print-CSS döljer avvikelse-sidofältet.
- Komplettering-fliken har 9 stackade sektioner utan navigering.
- Inga sökrutor i tabellerna.

---

## Faktarättelser (viktiga, för att inte upprepa felaktiga slutsatser)

Dessa har verifierats mot kod och docs - använd dem som styrande
sanning vid implementation:

### LKF-mappning ger enhetsskopning, inte direktjoin

Vägen finns: `KBR.agandeEnhetLkf → UnitAPI.lkf → UnitAPI.unitId →
Platser.owner.id`. Men:

- Det finns **inget** 1:1-ID mellan KBR-byggnad och Platser-plats.
- `KBR.facilityPartId` (UUID) matchar **inte** Platser-API v4
  (uttryckligt i `docs/modules/KBR.md` rad 164).
- En enhet (församling) har typiskt 1-5 kyrkor + flera andra byggnader.

**Korrekt användning:** namn-match först, LKF som filter när det finns
flera kandidater. Inte "ID-strikt" som första steg.

### `kbr_id == null` signalerar redan BV-only

För BV-only-typer (Församlingshem, Administrationsbyggnad, Krematorium,
Klockstapel) sätts `kbr_id: None` i `build_report.py` rad 568-622, och
`kbr_lat/kbr_lng` är då egentligen BV-koordinater.

UI:t kan kolla `r.kbr_id == null` för att veta detta. **Lägg inte till
ett `primary_source`-fält** - det är new API surface utan ny
funktionalitet.

### `report.csv` är ett externt kontrakt

`README.md` rad 43: "för rapportering till kyrkokansliet". Kolumnsetet
i `build_report.py` rad 736-739 är publikt format mot extern mottagare.

**Lägg till kolumner går bra. Ta bort eller döpa om är off-limits utan
samordning.**

### UI har redan separat BV-prick på kartan

`index.html` rad 504-509 ritar lila BV-prick på `bv_lat,bv_lng` med
polyline till KBR. För Kyrka/kapell finns alltså redan
multi-källa-visualisering. "primary_source saknas"-kritiken i
`rebuild.md` gäller bara BV-only-typer, och löses med `kbr_id == null`.

### Krematorium felmatchas mot kyrkogårdar

`build_report.py` rad 472-478 klassar `amenity=crematorium` som
`osm_typ="begravningsplats"`. Sedan rad 593-604 matchas BV-Krematorium
mot `osm_cemetery_by_name`. Bug.

---

## Implementationsplan

Steg 0 är en **utredning** (gå/inte-gå-beslut). Steg 1-7 är **commits**
på `rebuild`-branchen, var och en isolerat verifierbar.

### Steg 0: Utred LKF-mappning (1 eftermiddag, ej commit)

**Mål:** avgör om LKF-vägen fungerar för >80% av KBR-kyrkorna utan
manuellt arbete.

**Gör:**

1. För 20-30 slumpmässigt valda KBR-kyrkor: hämta `agandeEnhetLkf`.
2. Slå mot UnitAPI: `GET /units?$filter=lkf eq '<kod>'`. Få
   `unitId`.
3. Slå mot Platser: `GET /place?owner_id=<unitId>&is=churchandchapel`.
4. Bekräfta att kyrkan finns i resultatet (matcha på namn inom
   resultatet).

**Output:** kort anteckning i `rebuild-final.md` (ny sektion
"Steg 0-resultat") med:

- Hur många av 20-30 som mappades automatiskt.
- Kantfall: tomma `agandeEnhetLkf`, flera enheter på samma LKF, etc.
- Beslut: gå (>80% lyckas) eller inte-gå.

Om inte-gå: skippa steg 6, behåll nuvarande namn-match.

### Steg 1: Krematorium som egen OSM-typ

**Mål:** eliminera felmatchning Krematorium mot kyrkogård.

**Filer:** `kbr-kvalitet/build_report.py`

**Ändringar:**

1. Rad 472-478: skilj `crematorium` från `cemetery|grave_yard`. Lägg
   till `osm_typ="krematorium"` som egen typ.
2. Rad 593-604: matcha BV-Krematorium mot ny
   `osm_crematorium_by_name`-dict, inte mot `osm_cemetery_by_name`.

**Verifiering:**

- Kör `uv run kbr-kvalitet/build_report.py`.
- Inspektera `data/stats.json`: `krematorium_matchade` ska finnas och
  ha rimligt värde (matcha mot OSM ~50-100 svenska krematorier).
- Manuellt verifiera 2-3 träffar genom att klicka i UI:t.

### Steg 2: Bryt ut CSS + utils.js + map.js från index.html

**Mål:** möjliggör all framtida UI-iteration. 900-radersfilen
blockerar.

**Filer (nya):**

- `kbr-kvalitet/style.css`
- `kbr-kvalitet/js/utils.js` (`hvs`, `distColor`, `fmtDist`,
  `normalize`, `escapeHtml`, `setCount`, `rows`, `mapBtn`)
- `kbr-kvalitet/js/map.js` (Leaflet-init, `buildMarkers`,
  `renderUnmatched`, `jumpToKBR`, `highlightMarker`)

**Filer (ändras):**

- `kbr-kvalitet/index.html` - laddar via `<link rel="stylesheet">` och
  `<script src=...>` i rätt ordning.

**Funktionsändringar:** **inga**. Refaktor only.

**Verifiering:**

- Öppna i browser, klicka runt alla flikar, verifiera att UI ser
  identiskt ut.
- Verifiera att karta + filter + tabell-expansion funkar som förut.

**Anti-pattern:** **lägg inte till** bundler, ingen npm. Vanilla JS i
modul-filer laddade via `<script>`-taggar i rätt ordning.

### Steg 3: Tester för matchningslogiken

**Mål:** förutsättning för säker refaktor av match-koden.

**Filer (nya):**

- `kbr-kvalitet/tests/test_matching.py`

**Tester (minst):**

- `normalize("Sankta Maria") == normalize("S:ta Maria")` (om relevant)
- `normalize("  Härnösands   domkyrka  ") == "härnösands domkyrka"`
- `closest_match` med tom kandidatlista returnerar `(None, None)`
- `closest_match` returnerar närmaste inom `max_dist`
- `closest_match` returnerar `(None, None)` om alla kandidater är
  utanför `max_dist`
- `haversine` ger ~111000 m för 1° latitudskillnad
- `sweref_to_wgs84` ger korrekt resultat för en känd punkt
  (Linköpings domkyrka, kbr-id 32555)

**Kör med:**

```bash
uv run --with pytest pytest kbr-kvalitet/tests/
```

**Verifiering:** alla tester gröna.

### Steg 4: Lyft ut q_*-logiken till quality-plugins

**Mål:** separera kvalitetsanalys från fetch. Möjliggör steg 5
(caching).

**Filer (nya):**

- `kbr-kvalitet/quality.py` med:
  - En enkel `Finding`-dataclass (typ: str, kyrka: dict, info: dict)
  - Funktioner per kontroll (en per `q_*`-lista idag), tar list[dict]
    av råa KBR-poster, returnerar list[Finding]
  - `run_all_checks(churches: list[dict]) -> dict[str, list[Finding]]`
    som ger samma struktur som dagens `quality.json`

**Filer (ändras):**

- `kbr-kvalitet/build_report.py`:
  - Ta bort q_*-uppbyggnad ur fetch-loopen rad 162-262.
  - Behåll fetch-loopen som bara samlar `kbr_churches_raw` (alla
    KBR-fält).
  - Efter fetch: anropa `quality.run_all_checks(kbr_churches_raw)` för
    att bygga `quality.json`.

**Bevara:**

- `quality.json`-formatet **identiskt** med tidigare.
- Stats-värdena i `stats.json` ska vara identiska.
- `report.csv`-formatet **identiskt**.

**Verifiering:**

- Kör build före och efter steg. Diffa output:
  ```bash
  diff data/quality.json data/quality.json.before
  diff data/stats.json data/stats.json.before
  diff data/report.csv data/report.csv.before
  ```
  Inga ändringar förväntas.

**Anti-pattern:** ingen "plugin discovery", ingen registry-pattern,
inga abstrakta basklasser. Bara funktioner i en modul som anropas
explicit. Lekplats-projekt - YAGNI.

### Steg 5: Cache rådata + separera fetch/analyze

**Mål:** snabbare iteration. Möjlighet att uppdatera bara en källa.

**Filer (ändras):**

- `kbr-kvalitet/build_report.py` blir entry point med flaggor:
  - `--no-fetch` (använd cachen om den finns)
  - `--refresh=kbr,osm` (tvinga om vissa källor)

**Filer (nya):**

- `kbr-kvalitet/data/raw/kbr_churches.json` (TTL 24h)
- `kbr-kvalitet/data/raw/kbr_begravningsplatser.json` (TTL 24h)
- `kbr-kvalitet/data/raw/platser_*.json` (TTL 24h, en per typ)
- `kbr-kvalitet/data/raw/osm.json` (TTL 6h)
- `kbr-kvalitet/data/raw/_metadata.json` (timestamps per källa)

`data/raw/` ska vara gitignored (lägg till i `.gitignore` om saknas).

**Implementation:**

- Enkel cache-funktion i build_report.py (eller separat
  `cache.py` om den blir >50 rader): `fetch_or_cache(name, ttl_hours,
  fetcher_fn)`. Inget mer.
- Behåll **en** entry point. Ingen splittring i fyra fetch-skript.

**Snapshot-tillägg (samtidigt):**

Vid varje körning, skriv `data/snapshots/YYYY-MM-DD/{report,quality}.json.gz`
om dagens snapshot saknas. Gitignored. Inget UI för historik nu - bara
samla data.

**Verifiering:**

- Första körning: hämtar allt, skapar cache.
- Andra körning inom TTL: använder cache, klart på <10 sek.
- `--refresh=osm`: hämtar bara OSM, övrig cache bevarad.
- Snapshot finns i `data/snapshots/<dagens-datum>/`.

### Steg 6: LKF-filter i match-logiken (villkorat på steg 0)

**Mål:** eliminera kors-landsmatcher för generiska namn.

**Förkrav:** steg 0 visade att LKF-mappning fungerar.

**Filer (ändras):**

- `kbr-kvalitet/build_report.py`:
  - Ny fas: hämta `unitId` per `agandeEnhetLkf` från UnitAPI. Cacha
    som `data/raw/unit_lkf_map.json` (TTL 7 dygn - enhetsdata ändras
    sällan).
  - I match-loopen: när flera namnkandidater finns, filtrera först på
    `owner.id == mappad_unitId`. Om en kvar - klar. Annars
    närmaste-grann.
  - Lägg till fält `match_method` i `report.json`-rader: `"lkf"`,
    `"name"`, `"name+geo"`. **Inte i CSV** (för att inte bryta
    kontraktet).

**Verifiering:**

- Diffa `report.json` före och efter. Ändringar förväntas främst för
  generiska namn.
- Manuellt verifiera 5 fall där `match_method == "lkf"` löste
  tvetydighet som tidigare gav fel träff.

### Steg 7+: UI/UX-förbättringar

Implementera i ordning efter värde/insats. Varje punkt = en commit.

**Hög effekt, låg insats (gör först):**

1. Sortering visuellt indikerad (pilar i `<th>` på sorterad kolumn,
   pekare-cursor på sorterbara). I `js/utils.js` eller `js/table.js`.
2. "Rensa alla filter"-knapp i `#filter-panel`. Återställer
   `filterStift`, `filterTyp`, `filterSrc` och kör `applyFilter()`.
3. "Välj alla / Inverter"-länkar över Stift- och Typ-multiselect.
4. Sökruta i sidofältslistan (filter på namn-substring).
5. `bindPopup` istället för (eller utöver) `bindTooltip` på
   markörer. Mobil får click-popups.
6. Klickbara stat-counters: `<button>` som sätter threshold till
   5000 / 1000 / 200.
7. Print-CSS: visa avvikelse-listan i print-vyn (inte bara
   kvalitetsflikar).

**Medium effekt, medium insats:**

8. Sortering på kvalitetstabellerna (delad sorterings-kod).
9. Sökruta på alla kvalitetsflikar.
10. Sticky innehållsförteckning på Komplettering-fliken
    (chip-länkar till sektionerna).
11. URL-hash-state: persistera threshold + filter + aktiv flik +
    optional `kbr=<id>` för djup-länk till kyrka.
12. Loading-skeleton under datafetchen.

**Medium effekt, högre insats:**

13. Leaflet.markercluster vid utzoomad vy.
14. Logaritmisk threshold-slider (eller diskreta steg: 0, 50, 100,
    200, 500, 1000, 2000, 5000, 10000, 50000).
15. Färgkod / liten badge för byggnadstyp i sidofältslistan.
16. "Exportera CSV (filtrerad)"-knapp i `#coord-controls`.

**Snyggrättningar:**

17. KML-skydd-flagga i listvy (liten badge framför kyrknamnet).
18. `q-badge` font 12px, padding 2-8px (mer läsbar).
19. Fix `setCount`: `el.className = (n === 0) ? 'q-badge ok' :
    'q-badge'` oavsett `warn`-parameter (idag inkonsistent).

---

## Vad som EJ ska göras

- **Big-bang rewrite på separat branch.** Verktyget är operativt
  (CSV till kyrkokansliet), inkrementell migration är säkrare.
- **Lägg till `primary_source`-fält.** `kbr_id == null` signalerar
  redan BV-only.
- **Bundler / npm / TypeScript.** Vanilla JS, ingen build-step.
- **Skippa report.csv.** Externt kontrakt med kyrkokansliet.
- **Stift som markörfärg.** Kartan har redan färg per källa och
  per avvikelseintervall - tre axlar gör den oläsbar.
- **Heatmap.** Användarna granskar konkreta avvikelser, inte
  geografiska mönster.
- **Dashboard-vy med kvalitetsindex.** Demo-feature, inte
  arbetsverktyg.
- **Realtidsuppdatering.** Off-scope - data uppdateras manuellt.
- **Plugin-registry / abstrakta basklasser för quality-checks.**
  YAGNI - explicit funktionsanrop räcker.
- **Backwards-compat-shims.** Detta är ett enanvändar-verktyg, inga
  externa konsumenter förutom CSV-mottagaren.

---

## Branch och commit-konvention

- Branch: `kbr-kvalitet-rebuild` (svenskt, projektets konvention).
- En commit per steg (steg 0 dokumenteras direkt i denna fil).
- Commit-meddelanden på svenska, imperativ form:
  - "Bryt ut krematorium som egen OSM-typ"
  - "Dela upp kbr-kvalitet/index.html i moduler"
  - "Lägg till tester för match-logiken"
  - "Lyft ut kvalitetskontroller till quality.py"
  - osv.
- Inga `--amend`, inga `--no-verify`.
- Pusha inte utan att fråga.

---

## Acceptansvillkor för helheten

När alla steg är klara ska:

- [ ] `build_report.py` är <400 rader (efter att q_*-logiken flyttat
      ut).
- [ ] `quality.py` finns med alla 14 kontroller som funktioner.
- [ ] `index.html` är <300 rader (skal + flikar). All JS i `js/`,
      all CSS i `style.css`.
- [ ] `data/raw/` finns med cachade rådata.
- [ ] `data/snapshots/` finns med dagliga snapshots.
- [ ] Tester i `tests/` kör grönt.
- [ ] `report.csv`-formatet är identiskt med innan.
- [ ] `quality.json`-strukturen är identisk.
- [ ] Alla sju UI-flikar fungerar identiskt eller bättre.
- [ ] Mobil: tooltips/popups fungerar på touch.
- [ ] Print: alla flikar inkl. avvikelse-listan kommer med.

---

## Frågor som kan dyka upp under implementation

**Q: Steg 0 visade att LKF inte fungerar. Vad gör jag?**
A: Skippa steg 6. Övriga steg står kvar.

**Q: Ska jag flytta `bv_grundinstallning.csv` till JSON?**
A: Lågprioriterad förbättring. Behåll CSV som källa, men `serve.py`
serverar redan JSON via `/kbr-kvalitet/api/bv` - räcker.

**Q: Steg 4 ändrar `quality.json`-formatet något (t.ex. dict-nycklar).
Är det OK?**
A: Nej. Formatet är **identiskt**. UI:t läser specifika fält. Om
behov uppstår - separat commit, dokumentera ändringen.

**Q: Hur testar jag UI-ändringar?**
A: `./start.sh` startar lokal server på `http://ubuntu-ai:8088/`
(eller `localhost:8088`). Testa i browser, både desktop och mobil
emulering. Säg uttryckligen om något inte testats.

**Q: Vad gör jag med `rebuild.md`, `rebuild-opus.md`,
`rebuild-gemini.md`?**
A: Behåll under arbetet som referens. Vid merge till main: ta bort
eller flytta till `docs/`-arkiv. Detta dokument
(`rebuild-final.md`) kan också tas bort efter merge - eller
behållas som efteråt-rapport.

**Q: Ska jag uppdatera `README.md` för kbr-kvalitet?**
A: Ja, i sista steget. Reflektera ny filstruktur (modul-uppdelning),
tester, cache, snapshot. Tona ner BV-jämförelse om det är
sjunde-fliken eftersom README idag bara nämner sex.

**Q: `CLAUDE.md` på projektnivå?**
A: Inget akut behov - detta projekt har ingen projekt-CLAUDE.md
(bara root-nivå för `svk-api-playground`). Om filstrukturen blir
tillräckligt komplex kan en `kbr-kvalitet/CLAUDE.md` skapas i
sista steget.
