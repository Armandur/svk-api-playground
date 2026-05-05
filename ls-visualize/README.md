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

## Layout

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

## Filtrering

Sidopanelen toppright låter dig:
- Toggla Ja / Nej-färgning (gäller både polygoner och off-shore-badges)
- Toggla lager (enheter, stiftsgränser, off-shore-boxar)

Sidopanelen toppleft visar anslutningsgrad per stift, sorterad enligt
Unit-API:s skpkod.
