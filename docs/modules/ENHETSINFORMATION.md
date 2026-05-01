# Enhetsinformation

Levererar koder, info och kontaktinfo om Svenska kyrkans enheter
(stift, pastorat, församlingar, m.fl. organisatoriska nivåer).

## Snabbfakta

| Fält | Värde |
|---|---|
| Stil | REST (JSON) |
| Bas-URL prod | `https://api.svenskakyrkan.se/enhetsinfo/v2` |
| Auth | `?apikey=` eller `SvkAuthSvc-ApiKey: <key>` |
| Doc (HTML) | https://api.svenskakyrkan.se/enhetsinfo/v2/doc/ |
| Swagger | Saknas publikt |

Tjänsten listas bara i test-portalen, men dokumentationen och
prod-instansen ligger på prod-domänen och fungerar.

## Notering

Eftersom det inte finns en publik Swagger-fil måste man läsa HTML-doc:en
direkt för att se exakta paths och fältschema. Doc:en genereras av
`SvenskaKyrkan.Platform.DocFmt`.

```bash
# Hämta doc-HTML
curl -sL https://api.svenskakyrkan.se/enhetsinfo/v2/doc/ | less
```

## Relaterade tjänster

- **UnitAPI** ([UNITAPI](#UNITAPI)) - sökning av enheter kopplade till
  webbsidor och kalenderhändelser. Använder OData och har bredare
  kopplings-möjligheter.
- **Församlingssök** ([FORSAMLINGSSOK](#FORSAMLINGSSOK)) - mappar adress
  -> församling och returnerar `enhetsid` som matchar Enhetsinformation.

## TODO

- Hämta exakta endpoints och fältschema från doc-HTML:en när vi börjar
  använda denna tjänst på riktigt. Lägg till curl-exempel här då.
