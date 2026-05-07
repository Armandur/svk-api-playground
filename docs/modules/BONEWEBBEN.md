# Bönewebben (`be.svenskakyrkan.se/api`)

Driver Svenska kyrkans Bönewebb - sajten där man tänder digitala ljus
och skickar in böner. APIt är **publikt och utan autentisering** och
returnerar JSON med strukturen `{ "success": true, "data": ... }`.

Hittades inte via portalerna - upptäcktes 2026-05-07 genom att titta
på `https://be.svenskakyrkan.se/allhelgona/karta/` och dess XHR-anrop.

## Snabbfakta

| Fält | Värde |
|---|---|
| Stil | REST (JSON), GET + en POST för rapportering |
| Bas-URL | `https://be.svenskakyrkan.se/api/` |
| Auth | **Ingen** - helt öppet |
| Doc | Saknas - ej listad i någon SVK-portal |
| Användning | "Tända ljus", böner, allhelgonakartan |

## Datamodeller

### Thought (ljus eller bön)

| Fält | Typ | Beskrivning |
|---|---|---|
| `id` | int | Unikt ID |
| `type` | str | `"candle"` eller `"prayer"` |
| `text` | str \| null | Fritext (tom sträng `""` om inget angetts) |
| `color` | str | Färg (oftast tom) |
| `tags` | str[] | T.ex. `["allhelgona2025"]` |
| `created` | str | ISO 8601 UTC, t.ex. `"2025-11-01T20:11:12Z"` |
| `position_lat` | str \| null | Latitud (sträng med decimal) |
| `position_long` | str \| null | Longitud (sträng med decimal) |
| `has_other_type` | bool | Posten finns även som annan typ |
| `only_overview` | bool | Visas bara i listvy, inte på karta |
| `place` | Place \| null | Kopplad kyrka/plats |
| `event` | Event \| null | Kopplat event |

`/geo-positions/`-svaret returnerar en mindre variant: bara `id`,
`text`, `created`, `position_long`, `position_lat`, `type`,
`only_overview`.

### Place (kyrka/plats)

| Fält | Typ | Beskrivning |
|---|---|---|
| `id` | int | Unikt ID |
| `name` | str | T.ex. `"Björskogs kyrka"` |
| `slug` | str | URL-slug, t.ex. `"bjoerskogs_kyrka"` |
| `physical_place` | str \| null | Ort |
| `description` | str | Beskrivning |
| `count` | int | Antal ljus/böner (i geo-svar) |
| `position_lat` / `position_long` | str | Koordinater (i geo-svar) |

### Event

| Fält | Typ | Beskrivning |
|---|---|---|
| `id` | int | T.ex. `3539` |
| `name` | str | T.ex. `"Allhelgona"` |
| `slug` | str | T.ex. `"allhelgona"` |
| `description` | str | Texten på event-sidan |

## Filtertyper

Används som path-parameter:

| Värde | Returnerar |
|---|---|
| `candles` | Alla ljus (med och utan text) |
| `prayers` | Alla böner |
| `both` | Ljus + böner |
| `candles-with-text` | Bara ljus som har text |
| `both-with-text` | Ljus + böner som har text |

## Endpoints

### Enskilt inlägg

```
GET /api/prayer/{id}/
```

### Geo-positioner per tagg (kartvyn)

```
GET /api/geo-positions/tags/{tag}/{filtertyp}/{antal}/{offset}/
```

Returnerar individuella koordinater + aggregerade kyrkor:

```jsonc
{
  "success": true,
  "data": {
    "thoughts": [
      { "id": 857205, "created": "2026-03-31T12:45:43Z",
        "position_long": "14.572", "position_lat": "60.913",
        "type": "candle", "only_overview": false }
    ],
    "rooms": {
      "results": [
        { "count": 4, "name": "Björskogs kyrka", "slug": "bjoerskogs_kyrka",
          "position_lat": "59.447", "position_long": "15.957" }
      ]
    },
    "metadata": { "count": 16586 }
  }
}
```

### Geo-positioner per plats

```
GET /api/geo-positions/place/{place-slug}/{filtertyp}/{antal}/{offset}/
```

### Event - metadata + paginerad lista

```
GET /api/event/{event-slug}/
GET /api/event/{event-slug}/{filtertyp}/{antal}/{offset}/
```

Sista varianten stödjer `?only_overview=true|false`. `metadata.count` =
totalt antal poster för eventet.

### Plats - metadata + listor

```
GET /api/place/{place-slug}/
GET /api/place/{place-slug}/{filtertyp}/{antal}/{offset}/
```

`/api/place/{slug}/` returnerar `prayers`, `candles` och `latest`-listor
samt en `featured`-post i samma svar.

### Rapportera

```
POST /api/report/{id}/
Content-Type: application/x-www-form-urlencoded
reason=<text>
```

## Curl-exempel

```bash
# Metadata om allhelgona-eventet (totalt antal ljus + böner)
curl -s "https://be.svenskakyrkan.se/api/event/allhelgona/" | jq '.data.metadata, .data.candles.count, .data.prayers.count'

# Senaste 20 ljusen med text under allhelgona
curl -s "https://be.svenskakyrkan.se/api/event/allhelgona/candles-with-text/20/0/?only_overview=false" | jq '.data.thoughts[] | {created, text}'

# Alla geo-positioner i tag allhelgona2025 (paginera 1000 åt gången)
curl -s "https://be.svenskakyrkan.se/api/geo-positions/tags/allhelgona2025/candles/1000/0/" \
  | jq '.data | {count: .metadata.count, first: .thoughts[0]}'

# Aggregerade kyrkor med flest ljus
curl -s "https://be.svenskakyrkan.se/api/geo-positions/tags/allhelgona2025/candles/1000/0/" \
  | jq '.data.rooms.results | sort_by(-.count) | .[0:5]'

# En specifik kyrkas alla ljus
curl -s "https://be.svenskakyrkan.se/api/place/bjoerskogs_kyrka/candles/100/0/" | jq '.data.metadata'
```

## Pagination

Alla list-endpoints använder `/{antal}/{offset}/` i path. Rekommenderat
max för `antal` är 1000. Ingen "next page"-länk returneras - paginera
tills `thoughts`-arrayen är kortare än `antal`.

```python
# Hämta alla ljus i ett event
import httpx
batch, offset, all_candles = 1000, 0, []
while True:
    r = httpx.get(
        f"https://be.svenskakyrkan.se/api/event/allhelgona/candles/{batch}/{offset}/",
        timeout=60).json()
    thoughts = r["data"]["thoughts"]
    if not thoughts: break
    all_candles.extend(thoughts)
    if len(thoughts) < batch: break
    offset += batch
```

## Kända event-slugs

| Slug | Namn |
|---|---|
| `allhelgona` | Allhelgona |

Fler kan finnas - sluggen ligger i `event.slug` på varje thought.

## Fältnoteringar

- `created` är alltid UTC. Konvertera vid visning.
- `position_lat` / `position_long` är **strängar**, inte tal. Kan vara
  `null` om ljuset tänts via formulär utan karta.
- `text` är `""` (inte `null`) när inget angetts.
- `tags` är en array av strängar, `event` är ett objekt - de pekar ofta
  på samma sak från olika vinklar.
- `only_overview: true` betyder att posten inte ska visas på karta, bara
  i listvy.

## Pilot-projekt

[allhelgona-replay](../../allhelgona-replay/) - tidsreplay av tända ljus
under allhelgona2025 på Leaflet-karta.
