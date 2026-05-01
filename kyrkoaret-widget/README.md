# kyrkoaret-widget

Visar dagens kyrkohögtid med liturgisk färg, kyrkoårsdel och dagens
bibeltexter. Drivs av Svenska kyrkans publika
`webapi/api-v2/churchcalendar`-endpoint - inga API-nycklar behövs.

## Snabbstart

```bash
# Från repo-roten
./start.sh
# -> http://localhost:8088/kyrkoaret-widget/
```

Eller öppna `index.html` direkt i en browser - apiKey:n är publik
klientside-nyckel (samma som svenskakyrkan.se använder).

Se [`CLAUDE.md`](CLAUDE.md) för datalogik och TODO.
