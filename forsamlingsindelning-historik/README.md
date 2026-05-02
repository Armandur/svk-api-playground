# forsamlingsindelning-historik

Tidsslider 2008-2026 över Svenska kyrkans **pastorat** och
**församlingar**. Visar nya pastorat (med ingående församlingar),
ändrad sammansättning, upplösta pastorat, FörE-konverteringar
(församling med egen ekonomi) och rena namnbyten - år för år.

## Snabbstart

```bash
# 1) Bygg datafilerna (~500 MB nedladdning, ~70 MB resultat)
uv run forsamlingsindelning-historik/build_historik.py

# 2) Bygg om bara summary.json från befintliga geojson-filer
uv run forsamlingsindelning-historik/build_historik.py --rebuild-summary

# 3) Servera
./start.sh
# -> http://ubuntu-ai:8088/forsamlingsindelning-historik/
```

## Funktioner

- **Karta** med pastoratsgränser i vinrött ovanpå tunnare grå
  församlingsgränser. Pastorat-popup listar ingående församlingar.
- **Årsslider** 2008-2026 med tickmarks (datalist) och stegvis snäppning.
- **Play-knapp** (▶) autospelar tidslinjen 2 sekunder per år. Stoppas
  med ■ eller genom att dra slidern.
- **(i)-knapp** öppnar drawer med detaljerade förändringslistor.
  Knappen byter till × när drawer:n är öppen.
- **Highlight-färgning** av aktiv förändring: nya pastorat gröna,
  ändrade guld, upplösta mörkröd-streckade, tillagda församlingar
  gröna, borttagna mörkröda, stabila går i bakgrunden.
- **Färgkodade rubriker** i drawer:n med färgruta som matchar kart-stilen.
- **Toggle "Bara ändrade"** filtrerar bort stabila pastorat/församlingar.
- **Klick på rad i drawer:n** zoomar och öppnar popup på kartan.
- **Tooltips** visar status: "Nytt pastorat sedan X", "Bildat pastorat
  (tidigare X som FörE)", "Ändrad sammansättning: + tillagda, − borttagna",
  "Pastorat → FörE", "Skpkod-omkodning (ingen strukturell ändring)",
  "Upplöst {år}" + lista över vart församlingarna gick, "Tillagd i Y
  pastorat sedan X" / "Borttagen från Y".
- **URL-state**: `?year=YYYY` synkas båda riktningarna - dela en specifik
  vy genom att kopiera URL:en.
- **Mobilvänlig drawer** från botten med backdrop, öppnas/stängs via
  info-knappen som byter mellan (i) och ×.

## Förändringskategorier

| Kategori | Innebörd |
|---|---|
| **Nya pastorat** | Helt ny `skpkod` |
| **Bildat pastorat** | "X församling" → "Y pastorat" på samma `skpkod` (FörE som utökats till flerförsamlings-pastorat) |
| **Ändrad sammansättning** | Samma `skpkod`, andra ingående församlingar |
| **Pastorat sammanslaget till FörE** | "X pastorat" → "Y församling" på samma `skpkod` |
| **Upplösta pastorat** | `skpkod` försvinner; flerförsamlings-pastorat |
| **FörE upphör** | `skpkod` försvinner; var en församling med egen ekonomi |
| **Namnbyte** | Samma typ, annat namn (ej genitiv-s eller suffix-tillägg) |
| **Skpkod-omkodning** | Ny `skpkod` med samma namn och samma ingående - bara administrativ omkodning, ingen strukturell ändring |

## Data

`build_historik.py` hämtar två lager per år:

- `ekonomiska_enheter_<år>-01-01.zip` (= pastorat och självständiga
  församlingar med egen ekonomi, identifierade via `skpkod`)
- `forsamlingar_<år>-01-01.zip` (identifierade via `lkfkod`)

Båda simplifieras med Douglas-Peucker 100 m (topology-bevarande) och
reprojiceras SWEREF 99 TM → WGS84. Aggregering per kod via
`unary_union` så att varje år har en feature per ekonomisk enhet
respektive församling.

**Mapping pastorat → församlingar** beräknas geometriskt via STRtree:
för varje församling hittas det pastorat vars polygon innehåller
församlingens centroid.

**Datakvalitet-filter** för att inte räkna kosmetiska ändringar som
"namnbyten":

- Genitiv-s före "församling/pastorat/kyrkliga" ignoreras (`Tierp` ≡
  `Tierps`).
- Suffix-tillägg av " församling" ignoreras (`Bromma` ≡ `Bromma
  församling`) - tar bort över 1200 falska namnbyten 2014-2015.
- Suffix "pastorat" och "kyrklig samfällighet" bibehålls så
  terminologi-byten 2013-2014 (`X kyrkliga samfällighet` → `X pastorat`)
  fortfarande noteras.

## Stora steg under perioden

| År | Pastorat | Församlingar | Anteckning |
|---|---|---|---|
| 2008 | 795 | 1761 | startår, "kyrklig samfällighet" var samarbetsform |
| 2009-2010 | -313 församlingar | | stora pastoratsbildningen |
| 2013-2014 | -101 | | terminologireform: 207 "kyrklig samfällighet → pastorat" |
| 2017-2018 | | | 17 nya pastoratsbildningar (FörE → pastorat) |
| 2018-2019 | +63 nya pastorat | | |
| 2024-2025 | | | 3 nya pastoratsbildningar |
| 2026 | 568 | 1251 | senaste indelningen |

`data/`-mappen är gitignored - bygg lokalt.

## Tekniska detaljer

- Leaflet 1.9.4 med `preferCanvas: true` (3-10x snabbare för 1000+
  polygoner).
- Prefetch av föregående/nästa år efter setYear så slidern blir snabb
  efter första bytet.
- Datalist + ticks-bar bakom slidern för visuella snäppmarkeringar.
- 100dvh + env(safe-area-inset-bottom) för iOS Safari-kompatibilitet.
- Filer: `index.html` (skal), `app.css` (stilar), `app.js` (logik) -
  ingen bundler.
- Skpkod-omkodningar detekteras genom att para nya FörE/pastorat med
  upphörda av samma namn + ingående församlingar - 240 sådana över
  perioden 2008-2026, varav 62 år 2018-2019 ensamt.
