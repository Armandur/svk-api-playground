Här är den fullständiga rapporten. Jag har också återställt öppettiden för måndag till 16:00.

---

# Rapport: Reverse-engineering av Svenska kyrkans platsadministration (Content Studio)

**Datum:** 2026-05-01

**Plats testad:** Härnösands domkyrka (`5dab016f-18f3-4973-92d8-69779653a1ef`)

**Miljö:** admin.svenskakyrkan.se (externwebbens platsadministration, ej produktion)

---

## Sammanfattning

Platsadministrationens sparfunktion anropar **inte** den publika API-gatewayen (`api.svenskakyrkan.se/platser/v4`). Istället används en **intern reverse proxy** på samma domän: `PUT /webapi/api-v2/place/{id}`. Autentisering sker uteslutande via en **sessions-cookie** (`CS_UserSessionId`) som sätts vid SSO-inloggning. Ingen API-nyckel eller `Authorization: Bearer`-header skickas i anropet. CORS-policyn (`Access-Control-Allow-Origin: https://admin.svenskakyrkan.se`) begränsar åtkomst för browser-klienter på andra origins, men ett server-till-server-skript kan kringgå CORS och använda cookien direkt — med de begränsningar som beskrivs i Sektion 3.

---

## Sektion 1: API-nyckel-/token-extraktion

### Cookies

Fem cookies finns på admin.svenskakyrkan.se, varav tre är tekniska/analys-cookies:

| Cookie-namn | Längd | Format | Synlig från JS | Bedömd funktion |

|---|---|---|---|---|

| `CS_UserSessionId` | 124 tecken | URL-safe base64 (opaque, inga punkter) | Ja | **Primär sessions-token** för CMS-autentisering |

| `TS0174741b` | 202 tecken | Opaque hex-liknande | Ja | F5 BIG-IP / TrafficShield WAF-cookie (loadbalancer) |

| `AdminWebId` | 6 tecken | Numerisk | Ja | Intern user-ID (ej token) |

| `ai_user` | 47 tecken | Opaque | Ja | Azure Application Insights (klient-analys) |

| `ai_session` | 50 tecken | Opaque | Ja | Azure Application Insights (klient-analys) |

**CS_UserSessionId:**

\- Hämtas programmatiskt: `document.cookie.split(';').find(c=>c.trim().startsWith('CS_UserSessionId=')).split('=')[1]`

\- Format: URL-safe base64, 124 tecken, exempelprefix: `38ahNb...49gJo1`

\- Varken JWT (inget `eyJ`-prefix, inga punkter) utan ett opakt server-side sessionhandle

\- Sätts av ASP.NET Core Identity / FormsAuthentication efter lyckad SSO

\- Utgångstid: `sessionTimeout = 90 minuter` (inaktiv) enligt `window.churchContext.appSettings.sessionTimeout`

\- Troligen `HttpOnly; Secure; SameSite=Lax` (kan ej verifieras från JS, men HttpOnly är standard för ASP.NET-sessionscookies)

\- Refreshas **inte** automatiskt — ny cookie utfärdas vid ny SSO-inloggning

**Ingen JWT** hittades i localStorage, sessionStorage, IndexedDB eller globala JS-variabler.

---

### API-nycklar i `window.churchContext`

CMS laddar en inline JS-variabel `window.churchContext` (via `/churchcontext`) som innehåller:

| Nyckel | Värde (maskerat) | Används till |

|---|---|---|

| `clientSettings.placesApiKey` | `238db3...(36 tecken UUID)` | Publik läsnyckel mot `api.svenskakyrkan.se/platser/v4/` |

| `clientSettings.municipalityApiKey` | `07b5ac...(36 tecken UUID)` | Kommunregister-API |

| `appSettings.placesApiKey` | `18dc02...(36 tecken UUID)` | Intern platser-nyckel (server-side proxy) |

| `appSettings.articlesApiKey` | `18dc02...(36 tecken UUID)` | Samma nyckel som ovan |

| `appSettings.paymentFormsApiKey` | `02db29...(36 tecken UUID)` | Betalsystem-API |

Hämtas programmatiskt:

```js

window.churchContext.clientSettings.placesApiKey   // publik läsnyckel

window.churchContext.appSettings.placesApiKey       // intern nyckel

```

**Viktigt:** Ingen av dessa UUID-nycklar används som header i det faktiska PUT-anropet till `/webapi/api-v2/`. Se Sektion 2.

---

### Auth-flow / inloggning

```

Oautentiserad → GET /webapi/api-v2/place/{id}

            → 401 + Location: /webapi/api-v2/Account/Login?ReturnUrl=...

            → Redirect till externt SSO/SAML-IDP (federerad inloggning, AD-grupper via "KAP\\" och "Ext\\")

            → IDP-token valideras

            → ASP.NET utfärdar CS_UserSessionId-cookie

            → Klient är autentiserad

```

Grupperna i `churchContext.user.groups` visar Active Directory-prefixen `KAP`, `Ext`, `CS-BUILTIN` — detta är en **federated/SAML-baserad SSO** (troligen ADFS eller Azure AD).

---

## Sektion 2: Skriv-anropet

### Primärt anrop (öppettidssparning)

```

PUT https://admin.svenskakyrkan.se/webapi/api-v2/place/[GUID-maskerat]?

```

**Request headers:**

| Header | Värde |

|---|---|

| `Content-Type` | `application/json` |

| `Prefer` | `return=representation` |

| `Cookie` | `CS_UserSessionId=[124-teckens opaque token]; TS0174741b=[202 tecken]; AdminWebId=[6 siffror]; ai_user=...; ai_session=...` |

| `Origin` | `https://admin.svenskakyrkan.se` (automatisk) |

Inga `Authorization`, `Ocp-Apim-Subscription-Key`, `X-Api-Key` eller liknande headers skickas explicit. **`CS_UserSessionId` är det enda autentiserings-medlet** — skickas automatiskt av webbläsaren som cookie.

**Request body (sanerad — öppettidsstruktur):**

```json

{

 "id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",

 "name": "Härnösands domkyrka",

 "shortDescription": "...",

 "longDescription": "<html>...</html>",

 "owner": { ... },

 "placeTypes": [...],

 "parent": null,

 "published": "2016-05-03T08:38:...",

 "geolocation": { "lat": 62.63..., "lng": 17.94... },

 "geolocationInfo": { ... },

 "contactInfo": { ... },

 "visitingInfo": { ... },

 "openHours": {

   "info": "",

   "periods": [

     {

       "validFrom": "2022-03-17",

       "days": {

         "mo": [{ "from": "08:00", "to": "16:00" }],

         "tu": [{ "from": "08:00", "to": "16:00" }],

         "we": [{ "from": "08:00", "to": "16:00" }],

         "th": [{ "from": "08:00", "to": "16:00" }],

         "fr": [{ "from": "08:00", "to": "16:00" }],

         "sa": [{ "from": "08:00", "to": "16:00" }],

         "su": [{ "from": "08:00", "to": "13:00" }]

       }

     }

   ]

 },

 "categories": [...],

 "tags": [...],

 "placeDetails": { ... },

 "media": { ... }

}

```

Total bodystorlek: \~6 400 tecken (hela objektet skickas, inte bara ändrade fält — full replace).

**Response:**

| Fält | Värde |

|---|---|

| Status | `200 OK` |

| `api-supported-versions` | `2.0` |

| `access-control-allow-origin` | `https://admin.svenskakyrkan.se` |

| `access-control-allow-credentials` | `true` |

| `vary` | `Origin` |

| `x-proxy-destination` | `admin/api-v2` |

**Skillnad mot publik API (`api.svenskakyrkan.se/platser/v4/`):**

\- Intern: `PUT /webapi/api-v2/place/{id}` — **full replace**, skickar hela objektet

\- Publik: `PATCH /platser/v4/place/{id}` — partiell uppdatering, bara ändrade fält

\- Intern: fältet heter `openHours` (i payload); publik docs säger `openingHours` (eller `openHours` beroende på version — kontrollera mot `/platser/v4/doc/`)

\- GET-responsen från intern API har även `slug`, `created`, `updated` — men dessa behöver inte ingå i PUT-bodyn

\- Intern: `Prefer: return=representation` returnerar det uppdaterade objektet i response body

---

## Sektion 3: Kan jag återanvända nyckeln?

### Vad som krävs

Det enda som autentiserar skrivoperationen är `CS_UserSessionId`-cookien. Det finns ingen separat API-nyckel att extrahera. Frågan är alltså: **kan man ta ut den cookien och använda den utanför webbläsaren?**

### CORS-begränsning (browser-klienter)

`Access-Control-Allow-Origin: https://admin.svenskakyrkan.se` + `Vary: Origin` innebär att webbläsarbaserade klienter på andra origins blockeras. En Chrome Extension eller webbapp på annan host kan **inte** nå `/webapi/api-v2/` med fetch/XHR.

### Server-till-server (Node.js/Python-skript)

En server-side-klient bryr sig inte om CORS — det är en webbläsarkontroll. Om man kan läsa ut cookien och skicka den som `Cookie`-header i en HTTP-request fungerar det tekniskt, **under förutsättning att:**

1\. Cookien **inte** är `SameSite=Strict` (troligen `SameSite=Lax` eller `None` med `Secure`, men behöver verifieras med Chrome DevTools → Application → Cookies)

2\. Servern inte validerar att `Origin` eller `Referer` matchar — vi vet att `Vary: Origin` sätts, men vi kan inte säga om servern avvisar requests med annan/ingen origin (det återstår att testa)

3\. `CS_UserSessionId` sätts i Cookie-headern: `Cookie: CS_UserSessionId=38ahNb...49gJo1`

### Livstid och refresh

\- Timeout: **90 minuter** inaktivitet (från `appSettings.sessionTimeout`)

\- Ingen automatisk refresh-mekanism — vid timeout krävs ny SSO-inloggning (browser-baserad)

\- Det finns **inget token endpoint** att anropa programmatiskt för att refresha; `/webapi/api-v2/Account/Login` redirectar till SAML/ADFS-IDP som kräver browser-interaktion

### Scopes / behörighet

Behörigheten styrs av AD-gruppmedlemskap (`KAP\\redaktör_externwebb`, `Ext\\740_20271_*` osv.). Cookien ger enbart tillgång till de platser och enheter som den inloggade användaren har skrivrättighet till — **inte** alla platser i systemet.

### Rekommenderat tillvägagångssätt för pilotprojekt

**Kortsiktig lösning — manuell cookie-extraktion:**

```python

# .env

CS_SESSION=38ahNb...49gJo1   # hämtas från Chrome DevTools → Application → Cookies → CS_UserSessionId

# request

import httpx

headers = {

   "Cookie": f"CS_UserSessionId={CS_SESSION}",

   "Content-Type": "application/json",

   "Prefer": "return=representation",

}

# PUT hela place-objektet (full replace)

resp = httpx.put(

   "https://admin.svenskakyrkan.se/webapi/api-v2/place/{place_id}",

   json=place_payload,

   headers=headers

)

```

Observera att du **inte** behöver (och inte kan) sätta `Ocp-Apim-Subscription-Key` — det är det interna proxy-lagret som hanterar det om det ens används.

**Varning:** Om `SameSite=Strict` är satt på cookien, eller om servern validerar `Origin`-headern och avvisar requests utan korrekt origin, behöver du antingen:

\- Skicka `Origin: https://admin.svenskakyrkan.se` och `Referer: https://admin.svenskakyrkan.se/admin/platser/redigera` i din request, eller

\- Använda den publika APIM-gatewayen (`api.svenskakyrkan.se/platser/v4/`) och begära en prenumeration med skrivrättighet via Svenska kyrkans API-portal

**Långsiktig lösning:** Kontakta Nationell IT och begär en `Ocp-Apim-Subscription-Key` med write-scope för `/platser/v4/` — det är den dokumenterade och supportade vägen.

---

### Hur du läser av cookien i Chrome DevTools

1\. Öppna DevTools (F12)

2\. Application → Storage → Cookies → `https://admin.svenskakyrkan.se`

3\. Hitta `CS_UserSessionId` — notera värdet, `HttpOnly`-flaggan (om markerad kan den **inte** läsas via `document.cookie` utifrån, men du kan kopiera värdet här) och `SameSite`-inställningen

---

*Rapporten sparas enligt instruktion som `docs-from-claude-code-chrome/platser-edit-flow-2026-05-01.md`*
