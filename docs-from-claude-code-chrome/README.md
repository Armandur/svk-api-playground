# docs-from-claude-code-chrome

Rapporter genererade av Claude Code Chrome-extensionen från
inloggade webbsessioner (reverse-engineering av SVK:s interna
verktyg). Samma konvention som `medvind-mobil-poc/`.

Naming: `<feature>-<datum>.md`, t.ex.
`platser-edit-flow-2026-05-01.md`.

## Sanering

Inga API-nycklar, JWT-tokens, sessionscookies med värden, eller PII.
Maskerade så att strukturen syns men inte de faktiska värdena.

## Workflow

1. Användaren öppnar SVK:s interna verktyg i Chrome (inloggad).
2. Klistrar in en prompt från `prompts/` i Claude Code-extensionen.
3. Sparar resulterande markdown-rapport i denna mapp.
4. Claude (lokalt) läser in rapporten och drar slutsatser.

## Synk

Mappen är **protect-flaggad** i `scripts/watch_docs.py` så filer du
lägger i `/mnt/vmworkspace/svk-api-playground/docs-from-claude-code-chrome/`
direkt från en annan enhet *bevaras* trots att rsync använder
`--delete` på resten av repo:t.
