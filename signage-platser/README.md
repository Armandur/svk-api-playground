# signage-platser

Signage-vy som visar aktuella öppettider för en plats från Svenska
kyrkans Platser-API. Tänkt för en infällbar zon på en signage-skärm
utanför en kyrka.

## Snabbstart

```bash
# Sätt nycklar
export APIKEY_PROD=<din svk-prod-nyckel>
export PLACE_ID=5dab016f-18f3-4973-92d8-69779653a1ef   # Härnösands domkyrka

# Hämta data
uv run refresh.py

# Servera sidan
python3 -m http.server 8000
# Öppna http://localhost:8000/
```

Se [`CLAUDE.md`](CLAUDE.md) för full kontext, datakontrakt och
driftsättning.
