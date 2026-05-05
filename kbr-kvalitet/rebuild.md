# Rebuild: kbr-kvalitet

En designöversyn baserad på nuläget (maj 2026) - skriven som underlag för
diskussion med Opus/Gemini. Representerar vad jag skulle göra annorlunda om
jag byggde det från scratch idag, och vad som är värt att åtgärda nu kontra
vad som kan vänta.

---

## Vad verktyget gör (nuläge)

`build_report.py` (742 rader) hämtar data från fyra källor, matchar dem mot
varandra med namn + geografiskt avstånd, och skriver ut JSON-filer som
`index.html` (900 rader) konsumerar.

**Källor:**
- **KBR API** - kyrkor (med datumkvalitet, koordinater i SWEREF99TM) och
  begravningsplatser
- **SVK Platser API** - kyrka, parishhome, cemetery, secretariat
- **Overpass/OSM** - place_of_worship, cemetery, crematorium, campanile
- **BV CSV** (statisk fil) - Församlingshem, Administrationsbyggnad,
  Krematorium, Klockstapel

**Byggnadsetyper som matchas:**
- Kyrka/kapell: KBR → Platser + OSM (Platser primary, OSM sekundär)
- Begravningsplats: KBR begravningsplatser → Platser cemetery + OSM cemetery
- Församlingshem: BV → Platser parishhome (max 2km)
- Administrationsbyggnad: BV → Platser secretariat (max 2km)
- Krematorium: BV → OSM crematorium
- Klockstapel: BV → OSM campanile

**Output:**
- `data/report.json` - matchade rader (koordinatavvikelser)
- `data/quality.json` - datumkvalitet + koordinatkvalitet för KBR-kyrkor
- `data/stats.json` - aggregerad statistik
- `data/kbr_all.json` / `data/kbr_begravningsplatser.json` - rådata för karta
- `data/platser_extra.json` - rådata Platser övriga typer

---

## Grundproblem

### 1. Monolitisk pipeline utan caching

Varje körning hämtar ALL data från ALLA källor - KBR API (pagingad),
Platser API (pagingad per typ), Overpass (stor query), BV CSV. Det tar
uppskattningsvis 5-15 minuter och ger ingen möjlighet att uppdatera bara
en källa.

**Lösning:** Dela upp i oberoende fetch-steg med filbaserad cache och
tidsstämpel. Kör bara om om cachen är äldre än N timmar.

```
fetch_kbr.py        → data/raw/kbr_churches.json      (TTL: 24h)
fetch_platser.py    → data/raw/platser_*.json          (TTL: 24h)
fetch_osm.py        → data/raw/osm.json                (TTL: 6h)
build_matches.py    → data/report.json + quality.json  (körs alltid)
```

Alternativt: ett enkelt `build.py` med `--skip-fetch` om rådata är färsk.

### 2. Namnmatchning som enda matchningsstrategi

`closest_match()` matchar på `normalize(namn)` + geografiskt avstånd. Det
funkar bra för kyrkor (unika namn) men ger felträffar för generiska namn:
"Församlingshem", "Administrationsbyggnad", "Krematorium".

KBR returnerar `geografiskEnhetLkf` (LKF-kod för geografisk enhet) och
`agandeEnhetLkf`. Platser-API:t returnerar enhetsid. Om man kan mappa
LKF-kod → enhetsid direkt (via Enheter-API:t eller UNITAPI) kan man göra
exakt join istället för namnmatchning - det är ett helt annat kvalitetssteg.

Utan direkt ID-join är bästa förbättringen att:
- Sänka max_dist per typ (redan gjort för Församlingshem/Administrationsbyggnad)
- Lägga till OSM `amenity=community_centre` som fallback för Församlingshem
- Eventuellt matcha på enhetsprefix (om BV-namn följer mönstret
  `{EnhetsNamn} Församlingshem`, matcha mot Platser-enhetens namn)

### 3. primary_source saknas

För Församlingshem/Administrationsbyggnad/Krematorium/Klockstapel är
`kbr_lat`/`kbr_lng` i report.json egentligen BV-koordinater. UI:t visar
dem som "KBR" (röd prick), vilket är missvisande.

Varje rad bör ha ett `primary_source`-fält: `"kbr"` eller `"bv"`. UI:t
använder det för att sätta rätt etikett och färg på primärpricken.

### 4. index.html är för stor

900 rader blandat HTML/CSS/JS. Inga separata filer.

**Lösning:** Dela upp utan bundler:
```
index.html          # skelett + tabbar + CDN-imports
style.css           # all CSS
js/filters.js       # filterstate, multiselect-panel
js/map.js           # Leaflet-karta, markörer, unmatched-lager
js/table.js         # buildTable, row-detail
js/bv_tab.js        # BV-jämförelse-fliken
js/quality_tab.js   # Datumkvalitet-fliken
js/utils.js         # hvs, distColor, fmtDist, setCount, rows, normalize
```

Varje fil hålls under 200 rader. Laddas med `<script src="js/...">` i
rätt ordning.

### 5. BV-data är en statisk CSV

`bv_grundinstallning.csv` uppdateras inte automatiskt. `scripts/serve.py`
exponerar den som `/kbr-kvalitet/api/bv` men det är en engångsinläsning vid
serverstart.

Om BV har ett programmatiskt API (eller om exporten kan automatiseras) borde
det vara en fetch-steg precis som de andra källorna. Om det alltid är manuell
export är nuläget okej - men dokumentera att filen behöver uppdateras manuellt.

---

## Vad som är värt att åtgärda nu

Rangordnat efter effekt/insats:

| Prioritet | Ändring | Effekt |
|-----------|---------|--------|
| Hög | `primary_source`-fält + rätt etikett i UI | Korrekt visning av Församlingshem etc. |
| Hög | OSM `community_centre` som fallback för Församlingshem | Fler träffar för vanlig byggnadstyp |
| Medium | Cachad fetch (separata steg) | Snabbare iteration, möjlighet att uppdatera en källa |
| Medium | Dela upp index.html i separata JS/CSS-filer | Underhållbarhet |
| Låg | ID-baserad matchning via LKF-kod → enhetsid | Kräver kartläggning av Enheter-API |
| Låg | Koordinatprecisions-rapport för KBR och Platser (ej bara BV) | Mer komplett kvalitetsbild |

---

## Vad som förmodligen inte är värt att göra

- **Realtids-API**: Verktyget är ett batch-rapport-verktyg. Att göra det
  till en live-tjänst som alltid hämtar färsk data är överkurs för
  användningsfallet.

- **Databaserad lagring**: SQLite-modell med inkrementella uppdateringar och
  historik. Intressant på sikt, men JSON-filer räcker för nuläget.

- **Fuzzy namnmatchning**: Levenshtein-avstånd på namn. Ger för många
  falska träffar utan att man också har strik geografisk gräns. Bättre
  att satsa på ID-baserad matchning.

- **Automatisk omklassning av felträffar**: Svårt att göra rätt utan
  manuell validering. Bättre att filtrera bort tveksamma träffar (>2km
  för generiska namn) och visa dem som omatchade.

---

## Konkreta nästa steg (implementerbara nu)

1. **Lägg till `primary_source` i build_report.py**
   - `"primary_source": "kbr"` för Kyrka/kapell och Begravningsplats
   - `"primary_source": "bv"` för Församlingshem, Administrationsbyggnad,
     Krematorium, Klockstapel
   - I index.html: om `r.primary_source === "bv"`, visa "BV" istället för
     "KBR" på primärpricken

2. **Lägg till OSM community_centre i Overpass-queryn**
   ```
   node["amenity"="community_centre"]["name"](area.se);
   way["amenity"="community_centre"]["name"](area.se);
   ```
   Bygg `osm_parishhome_by_name` och använd som fallback i
   Församlingshem-matchning (max_dist=2000).

3. **Bryt ut CSS och JS från index.html**
   Börja med `style.css` och `js/utils.js` - de är oberoende av resten och
   sänker filstorleken direkt.

---

## Öppna frågor

- Kan LKF-kod från KBR (`geografiskEnhetLkf`) mappas mot enhetsid i
  Platser-API:t utan manuellt arbete? Kollar man i UNITAPI/ENHETSINFORMATION?

- Har BV ett programmatiskt API, eller är CSV-exporten det enda alternativet?

- Vad är faktiskt den bästa källan för koordinater per byggnadstyp?
  BV, KBR och Platser ger olika koordinater - vilken är "rätt"?
  (BV verkar ha högst precision för kyrkor, men vi vet inte för övriga typer.)

- Är det relevant att visa historisk avvikelse - d.v.s. om en koordinat i
  KBR/Platser har ändrats sedan föregående körning?
