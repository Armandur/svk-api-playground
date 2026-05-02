# KBR-tidslinje

Animerad karta över ~3 500 svenska kyrkobyggnader från år 1000 till idag,
baserad på KBR (Kyrkobyggnadsregistret).

Live: **https://armandur.github.io/svk-api-playground/kbr-tidslinje/**

## Kör lokalt

```bash
# Bygg datamängden (kräver APIKEY_PROD i env, ~30 s)
APIKEY_PROD=<nyckel> uv run build_data.py

# Starta servern (från repo-roten)
./start.sh
# Öppna: http://ubuntu-ai:8088/kbr-tidslinje/
```

## Animationen

- **Streckad ikon** - kyrkan är under byggnation (`nybyggnadFran` nådd)
- **Fylld ikon** - kyrkan invigd (`invigning` nådd), era-specifik symbol och färg
- Kyrkornas färgmättnad tonas ned med åldern - nybygda kyrkor syns tydligast,
  äldre tappar successivt mättnad till ett golv på 20% (vid 400+ års ålder)
- Nyare kyrkor visas ovanpå äldre i z-led
- Sliderpricken och årtalet byter färg med epoken
- Play/pause + hastighetskontroll

## Epoker

| Epok | År | Färg | Symbol |
|---|---|---|---|
| Medeltid | –1527 | Gyllenbrunt | Klockstapel + stenkyrka |
| Reformationen | 1527–1720 | Mörkrött | Nålspira |
| 1700-tal | 1720–1800 | Varm grå | Klotfinal, pyramidkap |
| 1800-tal | 1800–1900 | Amber | Gotisk spira, spetsbågsfönster |
| 1900-tal | 1900–2000 | Stålblå | Platt tornkrön, funktionalistisk |
| 2000-tal | 2000– | Teal | Böljande tak, flytande kors |

## Deployment

Byggs av `.github/workflows/osm-deploy.yml` (gemensam med osm-konsistenscheck).
- Schemalagd daglig körning: alltid om
- Push till `kbr-tidslinje/`: återanvänder cachad OSM-data, bygger bara KBR
- `data/churches.json` cachelagras i Actions-cache, invalideras om `build_data.py` ändras

## Tekniskt

- Leaflet + vanilla JS, ingen bundler
- SWEREF99TM → WGS84 via pyproj i build-steget
- `data/churches.json` gitignored (~850 KB), byggs lokalt eller av CI
- ~3 500 kyrkor från KBR prod-API, koordinater i SWEREF99TM (EPSG:3006)

## Notering om koordinater

Enstaka poster i KBR har felaktiga koordinater. Linköpings domkyrka
är ett känt fall (~11 km fel). SWEREF99TM-konverteringen är korrekt -
felet ligger i källdata.
