# forsamlingskarta-leaflet

Interaktiv karta över Svenska kyrkans platser med Leaflet + OpenStreetMap.
Klickbara markörer visar plats-info, ägar-församling, faciliteter och
länk till svenskakyrkan.se.

## Snabbstart

```bash
# Lokal proxy (från repo-roten med .env satt)
./start.sh
# -> http://ubuntu-ai:8088/forsamlingskarta-leaflet/
```

Eller hosta `index.html` var som helst och peka direkt mot SVK med
read-only-nyckel:

```
https://din-server/forsamlingskarta-leaflet/?apikey=<key>
```

## URL-parametrar

| Param | Beskrivning |
|---|---|
| `?apikey=<key>` | Read-only API-nyckel - hämta direkt mot SVK utan dev-server |
| `?owner_id=<id>` eller `?owner_id=<id1>,<id2>,...` | Filtrera på ägar-enhet (församling/pastorat) |
| `?nearby=<lon>,<lat>&radius=<m>` | Geosök inom radie i meter (WGS84-koordinater) |
| `?limit=<n>` | Max antal platser (default 500) |

### Exempel

```
# Härnösands pastorats platser
?owner_id=20271

# Platser inom 5 km från en punkt
?nearby=17.94,62.63&radius=5000

# Direkt mot SVK utan dev-server
?apikey=<key>&owner_id=20271
```

## TODO

- Församlingsgränser som lager (väntar på fix av öppna geoserver-API:t
  som returnerar 404 just nu, eller ZIP-baserad statisk version).
- Klusterning vid utzoomning - alternativ när alla 9474 platser visas.
- Filter via UI: stiftsväljare, plats-typ-checkboxar.
- Rita markörikoner per plats-typ (kyrka/kansli/kapell).

Se [`docs/modules/PLATSER.md`](../docs/modules/PLATSER.md) för
datakontrakt, filter-syntax och `geolocation`-formatet (WGS84,
ordning lon/lat).
