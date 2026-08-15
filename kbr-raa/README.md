# kbr-raa - korslänkningskvalitet KBR vs K-samsök

Tar varje kyrka i [Kyrkobyggnadsregistret](../docs/modules/KBR.md) som
har ett `identitetRAA`-fält (= BBR-id) och slår upp samma id mot
[K-samsök](../docs/modules/KSAMSOK.md) (`https://kulturarvsdata.se/raa/bbr/{id}`).
Jämför namnen och klassificerar:

- **match** - similarity >= 0.80 (Vadstena klosterkyrka i båda)
- **mismatch** - similarity < 0.80 (KBR säger "Linköpings domkyrka",
  BBR säger "ÖSTRA HARGS KYRKA")
- **not_found** - BBR-id okänt i K-samsök (HTTP 404)
- **error** - typiskt HTTP 410 Gone (BBR-objekt borttaget i RAÄ)
- **missing_id** - KBR-kyrkan saknar `identitetRAA` helt
- **duplicates** - samma BBR-id ligger på flera KBR-byggnader

K-samsök är öppet (CC0, ingen nyckel), så hela pipelinen kräver bara
SVK-nyckeln till KBR.

## Snabbstart

```bash
APIKEY_PROD=...  # eller APIKEY=
./start.sh                                  # http://ubuntu-ai:8088/
# Öppna http://ubuntu-ai:8088/kbr-raa/
```

## Bygg om data

```bash
APIKEY_PROD=... uv run kbr-raa/fetch_kbr.py     # ~3500 kyrkor från KBR (~30s)
uv run kbr-raa/check_ksamsok.py                 # parallellt mot K-samsök (~15s)
```

Output:

- `data/kbr.json` - alla kyrkor med grundfält
- `data/report.json` - klassificerade resultat + dubbletter + summary

## Stack

- Python 3.12, urllib + threading (inga deps utöver standard).
- difflib.SequenceMatcher för namnjämförelse - normaliserar med uppercase,
  S:T -> SANKT, "och" -> "&", strippar specialtecken.
- Vanilla JS UI som läser `data/report.json` direkt.

## Tröskelvärde

Match-tröskeln är `similarity >= 0.80` (se `MATCH_THRESHOLD` i
`check_ksamsok.py`). Sänk till 0.7 om många legitima namnvarianter
(t.ex. olika gamla namnformer) felklassas som mismatch.

## Vad rapporten visar

Status per körning 2026-05-13:

| Status | Antal | Andel |
|---|---|---|
| match | 2560 | 72.8% |
| missing_id | 348 | 9.9% |
| mismatch | 274 | 7.8% |
| error (HTTP 410) | 240 | 6.8% |
| not_found | 96 | 2.7% |
| duplicate-grupper | 10 | - |

Mer än 20% av KBR:s kyrkor har antingen saknad, ogiltig eller
felmappad BBR-koppling. Det är användbart underlag för en städ-rapport
till SVK:s KBR-team.
