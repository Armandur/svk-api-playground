# signage-platser

Signage-vy som visar aktuella öppettider för en plats från Svenska
kyrkans Platser-API. Tänkt för en infällbar zon på en signage-skärm
utanför en kyrka, eller som widget på en intern hemsida.

## Komma igång - tre upplägg

### 1. Enklast - URL med din API-nyckel (för icke-tekniska användare)

Om du redan har en read-only API-nyckel från Svenska kyrkans API-portal
(`api.svenskakyrkan.se`) räcker det att hosta `index.html` på vilken
webbserver som helst (eller Github Pages, en fil-server, en S3-bucket)
och skicka in nyckeln + plats-id som URL-parametrar:

```
https://din-server.example/signage-platser/?apikey=<din-nyckel>&place=<plats-uuid>
```

Klienten hämtar då direkt från `api.svenskakyrkan.se` (CORS är öppet).
Read-only-nycklar är OK att exponera så här - de kan bara läsa
och inte ändra något.

**Hitta plats-UUID:** logga in på `api.svenskakyrkan.se`-portalen,
gå till en plats du vill visa, leta efter UUID i URL:en eller i
admin-panelen.

### 2. Lokal proxy (för utvecklare)

Om du kör hela `svk-api-playground`-repot lokalt med
`./start.sh` så finns en SVK-proxy på `localhost:8088`. Då räcker
bara `?place=<uuid>` i URL:en - nyckeln läses från `.env` och stannar
server-sidigt.

```
http://ubuntu-ai:8088/signage-platser/?place=<uuid>
```

Smidigt under utveckling och om du vill skydda nyckeln helt.

### 3. Helt offline (för signage utan internet vid skärmen)

Om signage-skärmen inte har direkt internet-access kan du köra
`refresh.py` periodvis (cron) för att skriva en lokal `place.json`
som klienten läser. Sätt env-vars:

```bash
export APIKEY_PROD=<din-nyckel>
export PLACE_ID=<plats-uuid>
uv run refresh.py             # skriver place.json
```

Schemalägg via cron (t.ex. var 10:e min):
```cron
*/10 * * * * cd /path/to/signage-platser && APIKEY_PROD=... PLACE_ID=... uv run refresh.py
```

Och servera mappen statiskt med vilken HTTP-server som helst.

## URL-parametrar

| Param | Beskrivning |
|---|---|
| `?place=<uuid>` | Plats-UUID. Krävs för upplägg 1 och 2. |
| `?apikey=<key>` | Read-only API-nyckel. Bara för upplägg 1. |
| `?view=week\|rolling\|extended` | Schema-layout (default: `week`). |
| `?details=max\|min` | Visa eller dölj klocka, faciliteter, adress, footer. |

### `?view=<mode>`

| Värde | Beskrivning | Antal dagar |
|---|---|---|
| `week` (default) | Innevarande vecka, mån-sön | 7 |
| `rolling` | Idag och 6 dagar framåt | 7 |
| `extended` | Idag fram till slutet av nästa hela vecka | 8-14 |

### `?details=<mode>`

| Värde | Innehåll |
|---|---|
| `max` (default) | Klocka, faciliteter, adress/telefon/e-post, footer-tidstämpel |
| `min` | Endast plats-titel, status-kort, veckotabell, info-text |

### Exempel

```
# Lokalt med proxy
http://ubuntu-ai:8088/signage-platser/?place=<uuid>

# Direkt mot SVK med nyckel - kompakt 8-14 dagars vy
https://din-server/signage-platser/?apikey=<key>&place=<uuid>&view=extended&details=min
```

## Stylning - Svenska kyrkans grafiska profil

Vyn använder SVK:s officiella färger och typsnitt:
- Beige bakgrund (`#FFEBE1`) med vinröd accent (`#7D0037`)
- DM Sans + Spectral italic via Google Fonts

Se [`docs/modules/_brand.md`](../docs/modules/_brand.md) i repot för
fullständig palett och regler.

Se [`CLAUDE.md`](CLAUDE.md) för datakontrakt mot Platser-API:t och
detaljer kring driftsättning.
