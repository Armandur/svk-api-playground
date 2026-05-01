# platser-edit-app

Webb-app för att redigera öppettider på en plats utan Content Studio.
Sökflöde + veckoschema-editor + PATCH mot Platser-API:t.

## Snabbstart

```bash
# Från repo-roten - kräver APIKEY_PROD i .env
./start.sh
# -> http://ubuntu-ai:8088/platser-edit-app/
```

Servern proxar `/api/platser/*` mot Platser-API:t med vår nyckel
server-sidigt - klienten ser aldrig nyckeln.

Se [`CLAUDE.md`](CLAUDE.md) för datakontrakt och skriv-regler.
