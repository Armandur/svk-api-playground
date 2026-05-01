# Projekt: SVK API playground

Lekplats för utforskning av Svenska kyrkans publika API:er. Innehåller
**dokumentation per tjänst** plus utrymme för pilot-projekt som
konsumerar API:erna.

Repo:t är inte ett git-repo just nu (`is git: false`). Skapa `git init`
om/när vi vill versionshantera.

## Struktur

```
svk-api-playground/
  docs/
    svk-apis.html          # genererad single-page docs (97 KB, gitignored om vi initar git)
    modules/
      _overview.md         # introduktion + portaler + gemensam auth
      _quickref.md         # copy-paste curl-exempel per API
      _deprecated.md       # ersatta tjänster
      _todo.md             # planerade utforskningar + projektidéer
      CALENDARAPI.md
      CHURCHCALENDAR.md    # webapi/api-v2/churchcalendar (kyrkoåret + bibeltexter)
      ENHETSINFORMATION.md
      FORSAMLINGSKARTOR.md
      FORSAMLINGSSOK.md    # Flax
      KBR.md               # Kyrkobyggnadsregistret
      PLATSER.md
      UNITAPI.md           # Enheter v2, OData
      AMNESOMRADEN.md      # Kategorier och Taggar v2, OData
  scripts/
    build_docs.py          # md -> docs/svk-apis.html
    watch_docs.py          # rebuild on change
  tmp/                     # cachade swagger.json + portal-HTML från utforskning
  <projektnamn>/           # pilot-projekt får egna undermappar (se _todo.md)
```

## Kör

```bash
# Gemensam dev-server (auto-listar dokumentation + alla pilot-projekt)
uv run scripts/serve.py     # http://localhost:8088/

# Engångsbygge av docs
uv run scripts/build_docs.py

# Watcher under aktiv redigering (bygger om + speglar till vmworkspace)
uv run scripts/watch_docs.py
```

uv kör skripten med PEP 723-inline-deps - inga andra installationer
behövs.

`scripts/serve.py` lyssnar på port **8088** (övriga `~/workspace`-projekt
använder 5002, 6789, 8000, 8001, 8765, 9222 - 8088 är ledigt).
Auto-detekterar pilot-projekt (undermappar med `index.html`) och listar
dem på startsidan tillsammans med dokumentationen och OpenAPI-speccarna
i `docs/specs/`. Inga byggsteg per nytt projekt - lägg till en mapp
med `index.html` så syns det på `/`.

## Hur jag (Claude) ska använda detta

- **Vid frågor om ett specifikt API** - läs `docs/modules/<API>.md`
  först. Den innehåller bas-URL, autentisering, endpoints och verifierade
  curl-exempel.
- **Vid ny utforskning** - lägg fynd i rätt modul-fil och uppdatera
  `_todo.md` om något öppet förblir oklart. Bygg om HTML:en med
  `uv run scripts/build_docs.py`.
- **Vid pilot-projekt** - skapa undermapp `<projektnamn>/` med eget
  `README.md` och `CLAUDE.md`. Refera till modul-filerna istället för
  att duplicera dokumentation.
- **Externa länkar i docs** - prefer interna markdown-länkar
  `[Modul](MODUL.md)` så build-skriptet kan rewrite:a dem till
  in-page-anchors.
- **Innehållsstil** - varje modul-fil ska börja med en "Snabbfakta"-tabell
  följt av endpoints/exempel. Håll filerna under ~400 rader (lättare
  att hålla i context vid läsning).

## Autentiseringsnycklar

Sätt API-nycklar via env, inte i docs:

```bash
export APIKEY='din-svk-nyckel'                        # täcker de flesta tjänsterna
export AZURE_KEY='din-azure-apim-subscription-key'    # för CalendarAPI
```

Curl-exempel i modulerna använder `${APIKEY}` / `${AZURE_KEY}`.

Den enda hårdkodade nyckeln i docs är CHURCHCALENDAR-nyckeln
`139ff33b-4451-4f0f-b397-1f4ec9307a87` som är **publik klientside-nyckel**
(exponerad i webbplatsens JS).

## Status per tjänst

Se `docs/modules/_overview.md` för aktuell sammanställning. När en
tjänst får ny info (t.ex. när vi har en API-nyckel och kan testa
fler endpoints), uppdatera respektive modul-fil och **inte** API.md
på rotnivån (den är borttagen, all info ligger i modules/).

## Pilot-projekt

Pilot-projekt mot API:erna lever som **undermappar på `main`**, inte på
egna branches. Anledning: alla projekt läser samma `docs/modules/` -
branch-modellen skulle tvinga oss att rebase varje gång dokumentationen
växer. Lyft ut till egen branch eller eget repo först om ett projekt
växer till något som behöver egen deployment-cykel.

Konvention per projekt:

- Egen undermapp `<projektnamn>/` på roten.
- Eget `README.md` med snabbstart.
- Eget `CLAUDE.md` med stack, konfig, beroenden mot SVK-API:erna.
- Refera till modul-filerna i `docs/modules/` istället för att duplicera
  API-dokumentation lokalt.
- Eget `.gitignore` om projektet har egna data-/byggartefakter.
- Helst ingen ny bundler/ramverk - följ användarens default-stack
  (vanilla JS + HTML + CSS för UI, FastAPI/SQLite för backend).

Använd `git worktree add ../svk-<projektnamn> -b <projektnamn>` om du
vill jobba på flera projekt samtidigt utan att stash:a - men huvudgrenen
ska fortfarande vara `main`.

Aktuella pilot-projekt: se `docs/modules/_todo.md`.

## Relaterat

- **medvind-mobil-poc** - parallell-projekt med samma docs-arkitektur
  (modul-MD + build-script). Förlaga till detta projekt.
