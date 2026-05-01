# Församlingssök (Flax)

Slår upp församlings- och valdistriktstillhörighet för en punkt i
Sverige givet adress, adressplatsid (UUID) eller SWEREF 99 TM-koordinater.
Hanterar även generering av kartor.

## Snabbfakta

| Fält | Värde |
|---|---|
| Stil | REST (JSON) |
| Bas-URL | `https://flax.svenskakyrkan.se/flax/api/` |
| Version | 1.0.665 (2026-03-23) |
| Auth | `?apikey=` eller `SvkAuthSvc-ApiKey: <key>` |
| Doc | https://flax.svenskakyrkan.se/flax/api/doc/ |
| Verifierad | ✓ prod 2026-05-01 (efter villkorsacceptans) |

**Gotcha:** om du får HTTP 500
"`Unknown authentication status: TermsNotAccepted`" har du en giltig
nyckel men har inte accepterat användarvillkoren för Flax på portalen
ännu. Logga in på `https://api.svenskakyrkan.se/` och godkänn villkoren
på Flax-tjänsten.

## Endpoints

### `GET /forsamlingsid` - slå upp församling

Tre uppslag-lägen, välj en av dem per anrop:

#### 1. Adressplatsid (UUID)

Snabbast och mest precist. Stöder **flera UUID:er kommaseparerade**.

```
?adressplatsid=<uuid>[,<uuid>...]
```

#### 2. Adress

En adress per anrop. Frågetolkning är något luddig - skicka renad data.

```
?adress=<gata+nr>&postnr=<NNN+NN>&postort=<ort>
```

#### 3. SWEREF 99 TM-koordinater

En koordinat per anrop. `n` = northing, `e` = easting (meter).

```
?n=<northing>&e=<easting>
```

### Modifierare

- `&indelning=YYYY-MM-DD` - använd historisk församlingsindelning
  (default = nuvarande).

## Curl-exempel

```bash
export APIKEY='din-svk-api-nyckel'
BASE='https://flax.svenskakyrkan.se/flax/api'

# Adressplatsid (kan ange flera)
curl -s "${BASE}/forsamlingsid?adressplatsid=21837641-e46d-40e2-8c83-5cca373deab0,1dd15b1a-6228-4e53-851c-722564340a8d" \
  -H "SvkAuthSvc-ApiKey: ${APIKEY}" | jq

# Fri textadress
curl -s -G "${BASE}/forsamlingsid" \
  --data-urlencode "adress=Polacksgatan 10 C lgh 1001" \
  --data-urlencode "postnr=821 33" \
  --data-urlencode "postort=Bollnäs" \
  -H "SvkAuthSvc-ApiKey: ${APIKEY}" | jq

# Koordinater (SWEREF 99 TM)
curl -s "${BASE}/forsamlingsid?n=6800224&e=574676" \
  -H "SvkAuthSvc-ApiKey: ${APIKEY}" | jq

# Historisk indelning
curl -s "${BASE}/forsamlingsid?adressplatsid=21837641-e46d-40e2-8c83-5cca373deab0&indelning=2008-01-01" \
  -H "SvkAuthSvc-ApiKey: ${APIKEY}" | jq
```

## Datastruktur

JSON-array med en träff per inskickat uppslag:

```jsonc
[
  {
    "adressplatsid": "21837641-e46d-40e2-8c83-5cca373deab0",  // bara om man slog upp på UUID
    "adress": "Polacksgatan 10 C lgh 1001",                   // bara om man slog upp på adress
    "postort": "Bollnäs",                                     // dito
    "postnr": "821 33",                                       // dito
    "forsamlingsnamn": "Bollnäs församling",
    "lkfkod": "218303",                                       // Län-kommun-församling-kod (SCB)
    "enhetsid": 1996,                                         // SVK-enhetsid (matchar UnitAPI/Enhetsinformation)
    "skpkod": "011307",                                       // SVKs interna kod
    "status": "OK",
    "n": "6803775.715",                                       // koordinat-resultat
    "e": "576204.525"
  }
]
```

### Kodtyper

- **`lkfkod`** - SCB:s 6-siffriga kod (län 2 + kommun 2 + församling 2).
- **`enhetsid`** - heltal, samma id som UnitAPI använder.
- **`skpkod`** - Svenska kyrkans interna kod.
- **`status`** - `OK` eller felkod om uppslag misslyckades.

## Användningsfall

- Visa rätt församlings-info för en besökare baserat på deras adress.
- Direktrouting av kund-ärenden till rätt församlingskansli.
- Datavalidering: är denna adress inom församling X?
- Historiska analyser av indelningsändringar.

## Begränsningar

- Endast svenska adresser/koordinater.
- Adress-uppslag är "best effort" - en oklar adress kan ge sämre svar
  än ett UUID-uppslag.
- Returnerar bara *en* församling per uppslag - om en punkt ligger på
  gränsen får man närmaste träff.
