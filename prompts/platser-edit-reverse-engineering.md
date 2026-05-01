# Reverse-engineera Svenska kyrkans platsadministration

Prompt att klistra in i Claude Code-extensionen i Chrome när du är
inloggad på externwebbens platsadministration. Spara rapporten under
`docs-from-claude-code-chrome/platser-edit-flow-<datum>.md` (samma
mönster som medvind-mobil-poc har).

---

Hjälp mig reverse-engineera hur Svenska kyrkans interna platsadministration
(externwebben / Content Studio) **skriver öppettider** på en plats, och
hur jag kommer åt **min egen "interna" API-nyckel** som verktyget använder.

Jag har redan en publik API-nyckel via api.svenskakyrkan.se som har läs-
behörighet på `/platser/v4/`, men `PATCH /place/{id}` ger 403 Access
denied. När jag är inloggad i platsadministrationen kan jag däremot
skriva - alltså finns det en annan nyckel/token i den sessionen som jag
vill kunna extrahera och återanvända i ett eget pilot-projekt.

## Att göra

1. Navigera till en plats du har skrivansvar för i platsadministrationen.
2. Öppna DevTools → Network, filtrera på XHR/Fetch.
3. Ändra en öppettid (t.ex. lägg till en ny rad eller justera en
   befintlig tid) och tryck Spara.
4. Fånga **alla** nätverksanrop som triggas av sparningen, inklusive
   eventuella föregående token-/auth-anrop.
5. Sök i `localStorage`, `sessionStorage`, cookies (Application-tab),
   `IndexedDB`, och inline JS-variabler efter strängar som ser ut som
   API-nycklar (UUID-format `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`,
   eller längre opaque-tokens / JWTs). Notera var de hittas och hur
   de namnges.

## Rapportera

### Sektion 1: API-nyckel-extraktion

För varje hittad nyckel/token:

- **Plats** (cookie-namn, localStorage-key, JS-variabel)
- **Hur den läses programmatiskt** (`document.cookie`, `localStorage.getItem("X")`,
  `window.svkConfig.apiKey`, etc)
- **Format** (UUID, JWT, opaque) och längd
- **Maskera värdet** ("ab12...ef99" eller "Bearer eyJ... (124 tecken)")
- **Verkar den ha utgångstid?** (JWT exp-claim, cookie Max-Age,
  refresh-mekanism)
- Om JWT: dekoda payload-delen och rapportera `iss`, `aud`, `scope`,
  `exp`, `iat` (men maskera `sub` och andra personliga claims)
- **Hur troligen hämtas/refreshas den** vid inloggning? (Vilken endpoint
  utfärdar den? OAuth2-flow? SAML?)

### Sektion 2: Skriv-anropet

Per relevant nätverksanrop som triggas av Spara:

- **Full URL** (path + query, maskera GUID:er och egna ID:n)
- **HTTP-metod**
- **Request headers** - särskilt `Authorization`, `Cookie` (visa bara
  cookie-namnen, inte värdena), `Content-Type`, `X-*`-headers, `Origin`,
  `Referer`, `Ocp-Apim-Subscription-Key`. Maskera värdena på tokens.
  **Identifiera vilken av nycklarna från sektion 1 som faktiskt skickas
  med** - det är den vi vill kunna återanvända.
- **Request body** (sanerad - maskera PII men behåll fältnamn/struktur)
- **Response status + headers** (Location, Set-Cookie)
- **Response body** (sanerad)

Lyft fram särskilt:

- Är det `api.svenskakyrkan.se/platser/v4/place/{id}` som anropas, eller
  en annan URL (intern CMS-endpoint, Azure APIM)?
- Vilken auth-typ används - OAuth2 Bearer? SSO-cookie? Egendefinierad
  header?
- Om OAuth: vilken issuer, vilka scopes?
- Skiljer sig payload-formatet från den publika doc-en
  (https://api.svenskakyrkan.se/platser/v4/doc/)?

### Sektion 3: Kan jag återanvända nyckeln?

Bedöm:

- Är nyckeln **session-bunden** (cookie + samma origin) eller går den att
  ta ut och använda i ett separat verktyg från en annan host?
- Behöver requesten vissa specifika headers (Origin, Referer) som
  servern validerar mot, eller räcker själva token:en?
- Vilka endpoints + scopes verkar token:en ha tillgång till?
- Hur länge gäller den? Behöver vi periodiskt refresha den?
- Kort sagt: **kan jag plocka ut den efter inloggning, lägga den i en
  .env och låta mitt eget verktyg använda den för PATCH /place/{id}?**

## Format

Markdown med de tre sektionerna ovan, plus en sammanfattning överst.

## Sanering

Ingen PII, inga riktiga tokens, inga session-cookies med värden.
Behåll endast tillräckligt mycket för att rekonstruera *strukturen* av
anropen och peka ut hur jag själv hittar nyckeln när jag är inloggad.
