# Allhelgona-replay

Kartreplay av tända ljus på Svenska kyrkans
[Bönewebb](https://be.svenskakyrkan.se/allhelgona/karta/) under senaste
allhelgonahelgen. Hämtar data från det öppna API:et
`be.svenskakyrkan.se/api/geo-positions/tags/allhelgona2025/candles/`
och spelar upp tändningarna i tidsordning.

## Snabbstart

```bash
# Hämta datat (~500 KB JSON, en gång räcker)
uv run build_data.py

# Servera (från repo-roten)
cd ..
./start.sh
# -> http://localhost:8088/allhelgona-replay/
```

Mellanslag växlar play/paus. Hastighetsknapparna mappar sim-tid mot
wall-tid (1 tim/s = en simulerad timme per sekund). Slidern spolar fram
och tillbaka.

## Filer

- `index.html` - markup + Leaflet-CSS
- `style.css` - SVK-grafisk profil + kontroller
- `app.js` - canvas-overlay som ritar 16k+ ljus per frame, replay-loop
- `build_data.py` - paginerar `/api/geo-positions/...` och skriver
  `data/candles.json` (`[[ts, lat, lng], ...]`, sorterad ASC)

## Deploy

Bygger via `.github/workflows/pages-deploy.yml` till
`https://armandur.github.io/svk-api-playground/allhelgona-replay/`.
Bygget kör `build_data.py` dagligen så datat hålls aktuellt.
