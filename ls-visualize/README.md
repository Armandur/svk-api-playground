# ls-visualize

Visualisering på Leaflet-karta av vilka ekonomiska enheter inom Svenska
kyrkan som är anslutna till Löneservice.

Källdata kommer från `Löneservice.csv` på `/mnt/vmworkspace/`.

## Kör

```bash
# Rebuild av JSON från CSV (gör en gång efter att CSV:n uppdaterats)
uv run build_data.py

# Egen fristående server på 0.0.0.0:8989
uv run serve.py              # http://ubuntu-ai:8989/

# Eller via repo-servern (port 8088)
./../start.sh                # http://ubuntu-ai:8088/ls-visualize/
```

Modulen är fristående - alla data ligger i `data/`:

- `loneservice.csv` (kopia av Löneservice.csv)
- `loneservice.json` (genererad av `build_data.py`)
- `ekonomiska_enheter.geojson` (kopia av forsamlingskarta-leaflets fil)
- `stift.geojson` (samma)

## Layout

- Ekonomiska enheter färglagda mörkgrön (Ja) eller gold (Nej).
- Stiftsgränser ovanpå som streckade linjer.
- Enheter utan eget geografiskt område ritas som "off-shore-badges"
  i havet/insjö nära ankarstaden, med streckad pil till stiftsstadens
  centrum:
  - 13 stiftskanslier (rad där Stift==Enhet i CSV:n)
  - Trossamfundet Svenska kyrkan (nationell nivå, ankrar mot Uppsala)
  - 5 övriga enheter (Hovförsamlingen, Finska, Tyska S:ta Gertruds,
    Karlskrona Amiralitetsförsamling, Göteborgs begravningssamfällighet)

## Filtrering

Sidopanelen toppright låter dig:
- Toggla Ja / Nej / Saknas-färgning
- Toggla lager (enheter, stiftsgränser, off-shore-boxar)

Sidopanelen toppleft visar anslutningsgrad per stift.
