# ls-visualize

Visualisering på Leaflet-karta av vilka ekonomiska enheter inom Svenska
kyrkan som är anslutna till Löneservice.

Källdata kommer från `Löneservice.csv` på `/mnt/vmworkspace/`.

## Kör

```bash
# Rebuild av JSON från CSV (gör en gång efter att CSV:n uppdaterats)
uv run build_data.py

# Servern startas via repo-roten - ls-visualize plockas upp
# automatiskt som pilot-projekt på portalen.
./../start.sh                # http://ubuntu-ai:8088/ls-visualize/
```

Modulen är fristående - alla data ligger i `data/`:

- `loneservice.csv` (kopia av Löneservice.csv)
- `loneservice.json` (genererad av `build_data.py`)
- `ekonomiska_enheter.geojson` (kopia av forsamlingskarta-leaflets fil)
- `stift.geojson` (samma)

## Karta

- Ekonomiska enheter färglagda mörkgrön (Ja) eller vinröd (Nej).
- Stiftsgränser ovanpå som streckade linjer.
- Enheter utan eget geografiskt område ritas som "off-shore-badges"
  med streckad pil till sin förankringsstad. Pixel-baserad rendering
  med iterativ kollisionsupplösning gör att badges aldrig överlappar
  varandra oavsett zoom-nivå:
  - 13 stiftskanslier (rad där Stift==Enhet i CSV:n)
  - Kyrkokansliet (nationell nivå, ankrar mot Uppsala)
  - 5 övriga enheter (Hovförsamlingen, Finska, Tyska S:ta Gertruds,
    Karlskrona Amiralitetsförsamling, Göteborgs begravningssamfällighet)

### Toggle:bara lager

- **Storlekscirklar**: en cirkel per territoriell enhet med radius
  `sqrt(antal_konton) * 1500m`. Absolut skala - en enhet med 200 konton
  har samma cirkel oavsett stift. Default avstängd.
- **Stift-choropleth**: fyller stiftspolygonerna i en 5-stegs skala från
  vinröd (<20% anslutna konton) till mörk grön (>=80%). Hover ger
  sammanfattning per stift. Skala visas i panelen när lagret är aktivt.

## Filtrering och fokus

Filter-panelen (toppright på desktop):

- **Visa**: toggla Ja / Nej-färgning (gäller alla lager med statusfärger)
- **Stift**: dropdown som zoomar kartan till valt stift och döljer
  enheter utanför
- **Min storlek**: 0/25/50/100/200 konton - filtrerar bort små enheter
- **Lager**: toggle för enheter, stiftsgränser, off-shore-boxar,
  storlekscirklar och choropleth

## Statspanel

Toppleft på desktop (eller via "Statistik"-knappen i mobilläget) - fyra
flikar:

- **Översikt**: två donuts som visar % anslutna enheter och %
  anslutna konton. Båda totaler från hela landet.
- **Per stift**: tabell med Ja/Tot för enheter och konton per stift,
  inklusive Trossamfundet (Kyrkokansliet) och en summa. Inline-stapel
  visualiserar % anslutna konton per stift.
- **Största ej-anslutna**: top-10-lista med de största ej-anslutna
  enheterna. Klick zoomar kartan till respektive enhet och öppnar
  popup. Off-shore-enheter (utan polygon) zoomar istället till sin
  anchor-stad.
- **Storleksfördelning**: histogram över enhetsstorlek (bins: <25,
  25-49, 50-99, 100-199, 200+ konton), staplat Ja/Nej.

## Popup på enhet

Klick på en territoriell enhet visar:

- Namn, stift och anslutningsstatus
- Antal konton
- Stiftskontext: % anslutna konton som mini-stapel + antal enheter
  och konton för stiftet, så man kan placera enheten i sitt sammanhang.

## Delbara vyer

Aktiv flik, stift-fokus, min-storlek, status- och lager-toggles sparas
i URL-hashen. Bara avvikelser från default skrivs ut, så basal URL är
ren. Stödjer browser-back/forward.

Exempel:

```
?#stift=Lunds%20stift&min=50&accounts=1
?#tab=top&choropleth=1
```

## Mobil-UI

På bredder <=700px byts panelernas position ut mot en knapprad nere
till vänster: **Statistik / Filter / Förklaring**. Klick öppnar
respektive panel som bottom-sheet (75% av viewport-höjd, slide-in).
Knappradens underkant linjeras dynamiskt med zoom-out-knappens
position så den aldrig täcker Leaflet-attributionen.

I mobil-tabellen döljs enhets-kolumnerna - bara konton + stapel visas.

## Idéer

Se [todo.md](todo.md) för diagram-idéer som inte är implementerade.
