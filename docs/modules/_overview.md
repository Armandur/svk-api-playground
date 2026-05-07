# Översikt - Svenska kyrkans API:er

Sammanfattning av alla publika API:er som drivs av Svenska kyrkan.
Genomgången gjordes 2026-04-30 mot prod- och testportalen samt deras
underliggande management-API:er och dokumentationssidor.

## Portaler och åtkomst

| Portal | URL | Funktion |
|---|---|---|
| Prod-portal | https://api.svenskakyrkan.se/tjanster | Tjänstekatalog för publika prod-API:er |
| Test-portal | https://api-t.svenskakyrkan.se/tjanster | Tjänstekatalog för test (delvis kyrknät-only) |
| Azure APIM (CalendarAPI) | https://svk-apim-prod.developer.azure-api.net/ | Endast CalendarAPI ligger här |
| Azure APIM (test) | https://svk-apimgmt-test.developer.azure-api.net/ | CalendarAPI test-instans |

API-nyckel skaffas via portalen efter inlogg. Man kan även **läsa**
management-API:et på Azure utan auth - se sektionen längst ner.

## Tjänster - sammanställning

Verifieringsstatus per 2026-05-01 med två separata nycklar (test +
prod). "✓" = HTTP 200 med vår nyckel; "✗" = nyckeln avvisas / saknad
prenumeration; "(öppet)" = ingen auth krävs.

| Tjänst | Stil | Modul-fil | Bas-URL prod | Prod-auth | Test-auth |
|---|---|---|---|---|---|
| Bönewebben | REST | [BONEWEBBEN](#BONEWEBBEN) | `https://be.svenskakyrkan.se/api/` | (öppet) | - |
| CalendarAPI | REST + OAuth2 | [CALENDARAPI](#CALENDARAPI) | `https://svk-apim-prod.azure-api.net/calendar/v1` | ✓ Azure-key | - |
| Kyrkoåret + bibeltexter | REST | [CHURCHCALENDAR](#CHURCHCALENDAR) | `https://www.svenskakyrkan.se/webapi/api-v2/` | ✓ publik nyckel | - |
| Enhetsinformation | REST | [ENHETSINFORMATION](#ENHETSINFORMATION) | `https://api.svenskakyrkan.se/enhetsinfo/v2` | ✗ 403 Access denied | ✗ 302 |
| Församlingskartor | OGC WMS/WFS | [FORSAMLINGSKARTOR](#FORSAMLINGSKARTOR) | `https://flax.svenskakyrkan.se/geoserver/uff/` | (öppet) | (öppet) |
| Församlingssök (Flax) | REST | [FORSAMLINGSSOK](#FORSAMLINGSSOK) | `https://flax.svenskakyrkan.se/flax/api/` | ✓ prod | ✗ |
| Kyrkobyggnadsregistret | REST | [KBR](#KBR) | `https://api.svenskakyrkan.se/kbr/api/` | ✓ prod | ✗ 302 |
| Platser | REST | [PLATSER](#PLATSER) | `https://api.svenskakyrkan.se/platser/v4` | ✓ prod | ✗ 401 |
| UnitAPI (Enheter v2) | OData | [UNITAPI](#UNITAPI) | `https://api.svenskakyrkan.se/externwebb/api-v2/odata/` | ✓ prod | ✓ test |
| Ämnesområden v2 | OData | [AMNESOMRADEN](#AMNESOMRADEN) | `https://api.svenskakyrkan.se/externwebb/api-v2/odata/` | ✓ prod | ✓ test |
| Calendar Search, calendarserviceapi | (ersatt) | [\_deprecated](#_deprecated) | - | - | - |

**Anteckningar:**

- Test- och prod-nycklar är **separata**. Vår test-nyckel ger 200 mot
  `externwebb/api-v2/odata` på test men 401 mot prod, och vice versa.
- **Flax/Församlingssök** krävde att man accepterar användarvillkor på
  portalen innan nyckeln började fungera (annars HTTP 500
  "Unknown authentication status: TermsNotAccepted").
- **Enhetsinformation** kräver fortfarande separat prenumeration -
  status 403 "Access denied". Tjänsten kanske är begränsad till
  internanvändning.
- **Bönewebben** är inte listad i någon SVK-portal - upptäcktes via
  `be.svenskakyrkan.se/allhelgona/karta/`. Helt öppet, ingen nyckel.

## Gemensam autentisering

De flesta tjänsterna använder samma mönster - en SVK-utfärdad API-nyckel
som skickas med på ett av två sätt:

```bash
# Som queryparameter
curl 'https://api.svenskakyrkan.se/<tjänst>/<resurs>?apikey=<API-NYCKEL>'

# Som HTTP-header (fungerar likvärdigt)
curl -H 'SvkAuthSvc-ApiKey: <API-NYCKEL>' \
     'https://api.svenskakyrkan.se/<tjänst>/<resurs>'
```

Utan giltig nyckel returneras typiskt `403 Not Authorized` (Platser) eller
`401 Unauthorized` (KBR).

**Undantag:**

- **CalendarAPI** ligger på Azure APIM - använd `Ocp-Apim-Subscription-Key`-header
  eller `?subscription-key=<key>`.
- **Kyrkoåret/bibeltexter** (`webapi/api-v2/churchcalendar`) använder bara
  `?apiKey=` (kamelKas). En publik klientside-nyckel finns
  i webbplatsens JS:`139ff33b-4451-4f0f-b397-1f4ec9307a87`.

## Miljöer

| Miljö | Domän | Anteckning |
|---|---|---|
| Prod | `api.svenskakyrkan.se` | Publik, kräver registrerad nyckel |
| Test | `api-t.svenskakyrkan.se` | "Endast inom kyrknätet" - vissa tjänster svarar inte alls publikt |
| GeoServer | `flax.svenskakyrkan.se` | Församlingskartor (WMS/WFS) + Församlingssök |
| Webbplats-API | `www.svenskakyrkan.se/webapi/` | Internt API som driver svenskakyrkan.se |
| Azure APIM | `svk-apim-prod.azure-api.net` (gateway) + `.developer.azure-api.net` (portal) | Endast CalendarAPI |

Test-portalen listar fler tjänster än prod, men flera av dem är inte
nåbara från publika nätverk (kräver kyrknätet).

## Azure APIM - öppen management-introspektion

CalendarAPI:s metadata kan läsas utan auth via management-API:et:

```bash
BASE='https://svk-apim-prod.management.azure-api.net/subscriptions/000/resourceGroups/000/providers/Microsoft.ApiManagement/service/svk-apim-prod'

# Lista publika produkter
curl -s "${BASE}/products?api-version=2022-04-01-preview" | jq

# Lista API:er
curl -s "${BASE}/apis?api-version=2022-04-01-preview" | jq

# Operationer för CalendarAPI
curl -s "${BASE}/apis/calendarapi/operations?api-version=2022-04-01-preview&\$top=200" | jq
```

URL:en kommer från `https://svk-apim-prod.developer.azure-api.net/config.json`.
Test-instansens motsvarighet är `svk-apimgmt-test.management.azure-api.net`.

## Konventioner i denna dokumentation

- **Bas-URL** anges för prod om inget annat anges.
- **`{var}`** = path-parameter, **`?<var>=`** = queryparameter.
- Curl-exempel använder `${APIKEY}` som plats-hållare. Sätt med
  `export APIKEY=...` eller `direnv` lokalt.
- Modul-filerna i `docs/modules/` är källan; HTML-bygget är genererat
  och ska inte editeras direkt.
