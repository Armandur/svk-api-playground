# signage-platser

Signage-vy som visar aktuella öppettider för en plats från Svenska
kyrkans Platser-API. Tänkt för en infällbar zon på en signage-skärm
utanför en kyrka.

## Snabbstart

```bash
# Sätt nycklar
export APIKEY_PROD=<din svk-prod-nyckel>
export PLACE_ID=5dab016f-18f3-4973-92d8-69779653a1ef   # Härnösands domkyrka

# Hämta data (skriver place.json)
uv run refresh.py

# Servera via repots gemensamma server
uv run ../scripts/serve.py
# Öppna http://localhost:8088/signage-platser/
```

## URL-parametrar

Alla kombinerbara - sätts på query-strängen.

### `?place=<guid>`

Hämta valfri plats live via dev-serverns SVK-proxy istället för
`place.json`. Användbart för att testa olika platser utan att köra
om `refresh.py`.

```
?place=5dab016f-18f3-4973-92d8-69779653a1ef   # Härnösands domkyrka
```

Utan parameter används `place.json` (default refresh.py-flöde).

### `?view=<mode>`

Vilka dagar som visas i schemat.

| Värde | Beskrivning | Antal dagar |
|---|---|---|
| `week` (default) | Innevarande vecka, mån-sön | 7 |
| `rolling` | Idag och 6 dagar framåt | 7 |
| `extended` | Idag fram till slutet av nästa hela vecka | 8-14 |

### `?details=<mode>`

Vilka extrasektioner som visas.

| Värde | Innehåll |
|---|---|
| `max` (default) | Klocka, faciliteter, adress/telefon/e-post, footer-tidstämpel |
| `min` | Endast plats-titel, status-kort, veckotabell, info-text |

### Exempel

```
/signage-platser/                                              # default
/signage-platser/?view=extended                                # 8-14 dagar
/signage-platser/?details=min                                  # kompakt zon
/signage-platser/?place=<guid>&view=rolling&details=min        # alla tre
```

Se [`CLAUDE.md`](CLAUDE.md) för full kontext, datakontrakt och
driftsättning.
