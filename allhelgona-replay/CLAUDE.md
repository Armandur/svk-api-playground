# allhelgona-replay - Claude-anteckningar

Pilot-projekt under [`svk-api-playground`](../CLAUDE.md). Visar tända
ljus från Bönewebbens publika API som en tidsbaserad replay på en
Leaflet-karta.

## Stack

- Vanilla JS + HTML + CSS, ingen bundler
- Leaflet 1.9.4 från unpkg (CDN)
- CartoDB DarkMatter-tiles (mörk natt-stämning passar flammor)
- Egen `L.Layer`-extension `CandleLayer` som ritar alla tända ljus per
  frame på ett `<canvas>` ovanpå mapPane. 16k+ `L.circleMarker`
  skulle vara segt - canvas är fler tiopotenser snabbare.
- `uv run build_data.py` hämtar data via PEP 723-inline-deps
  (`httpx`)

## Datapipeline

`build_data.py` paginerar `GET /api/geo-positions/tags/allhelgona2025/candles/{1000}/{offset}/`
tills tomt svar. Tag:en är hårdkodad till `allhelgona2025` (senaste
helgen). Output är `data/candles.json` i kompakt array-format:

```json
{
  "tag": "allhelgona2025",
  "fetched": "...",
  "count": 16586,
  "first_lit": "2025-04-01T07:18:22Z",
  "last_lit":  "2026-03-31T12:45:43Z",
  "candles": [[1730476313, 60.913, 14.572], ...]
}
```

Sorteras ASC på `ts` redan i bygget så klienten slipper. Koordinater
avrundas till 5 decimaler (~1 m) - filstorlek ~500 KB.

API-dokumentation: se `_underlag/bonewebben-api.md` om jag återbesöker
projektet, eller `/mnt/vmworkspace/bonewebben-api.txt` (ursprunget).
Inga API-nycklar - öppet API.

## Designval

- **Replay-tid mappad till sim-sek/wall-sek.** 4 hastigheter:
  600x, 3600x (default), 21600x, 86400x. 95 % av ljusen tänds inom
  ~8 dagar (21 okt - 4 nov 2025), så 1 tim/s ger ~3 min replay för
  helgen.
- **Pulse-effekt** på de senaste `PULSE_BUFFER = 200` tända ljusen.
  Pulse-längd är fast i wall-sek (`PULSE_DURATION_MS`) men beräknas i
  sim-sek via aktuell speed; en snabbare playback ger kortare pulse i
  reell tid men samma "felupplevelse".
- **Slider** spolar fram och tillbaka. `rewindLitIndex()` rensar ljus
  som inte längre är tända vid spolning bakåt.
- **CartoDB DarkMatter** valdes över ljus tile-källa - flammor syns
  bara mot mörk bakgrund. SVK-paletten (vinröd, beige) sitter i
  overlays, inte på själva kartan.

## Vanliga ändringar

- **Byta år/tag**: ändra `TAG` i `build_data.py` och `meta-tag`/`info-tag`
  defaults i `index.html`. Klienten extraherar årtal från `data.tag`
  vid load.
- **Ändra hastigheter**: `data-speed`-attribut i `<button>`-elementen
  i `index.html`.
- **Ändra pulse-stil**: konstanter överst i `app.js` + `drawCandles()`.

## Att testa

`./start.sh` på repo-roten startar servern på port 8088. Live på
`http://ubuntu-ai:8088/allhelgona-replay/` (eller `localhost`).

## Inte testat (ännu)

- Mobila enheter - layouten har media query <600 px men jag har inte
  verifierat i webbläsare på mobil.
- Spolning bakåt vid play (slider event under spelning) - kan ge race
  med tick-loopen om den är aktiv. Inte sett problem men inte testat.
