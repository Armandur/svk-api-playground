# PDF-bokhylla på GitHub Pages

Detta är ett tunt publiceringslager för PDF-bokhyllan i
[`Armandur/bokhylla`](https://github.com/Armandur/bokhylla). Ingen frontend-
eller läsarkod kopieras hit. Pages-bygget checkar ut den commit som anges i
`config.json` och kör dess statiska exportör.

De publicerade vägarna är:

- `/pdf-bokhylla/kyrkoordningen/`
- `/pdf-bokhylla/alla-bestammelser/`
- `/pdf-bokhylla/biskopsbrev/`

## Lokal byggning

```bash
uv sync --directory ../bokhylla/backend --frozen
SVK_ODATA_API_KEY="$SVK_ODATA_API_KEY" \
  python3 pdf-bokhylla/build.py \
  --bokhylla ../bokhylla \
  --mal _deploy/pdf-bokhylla \
  --pages-rot _deploy
```

`config.json` tillåter fyra verifierat otillgängliga äldre SvKB-dokument.
Alla nya bortfall stoppar bygget i stället för att ge en tyst ofullständig
publicering.

## GitHub Actions

Repo:t behöver följande Actions-secrets:

- `BOKHYLLA_READ_TOKEN`: read-only token för checkout av bokhylla-repot.
- `SVK_ODATA_API_KEY`: OData-nyckeln som PDF-källorna kräver vid byggning.

Nyckeln används endast av byggprocessen. Validatorn söker igenom hela
PDF-artefakten och stoppar bygget om nyckeln har råkat skrivas ut. Verifieringen
i Chromium kontrollerar separat att inga lokala serveradresser anropas.

## Storlek

Den verifierade exporten från TASK-1198 är 460 MiB och 4 755 filer. Det är
under GitHub Pages publiceringsgräns på 1 GiB men nära nog för att bevakas.
Bygget stoppar vid 900 MiB för PDF-delen eller 950 MiB för hela Pages-sajten.
Om gränsen nås ska PDF:er och sidbilder flyttas till GitHub Releases eller
objektlagring, medan HTML/JS och manifest kan ligga kvar på Pages.
