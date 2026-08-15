# kbr-raa - Claude-anteckningar

## Syfte

Kvalitetskontroll av KBR:s `identitetRAA`-fält. Resultatet visar hur
ofta KBR:s BBR-länk faktiskt pekar på rätt objekt i RAÄ:s
Bebyggelseregister.

## Pipeline

```
fetch_kbr.py        --> data/kbr.json       (alla kyrkor, ett anrop per 100)
check_ksamsok.py    --> data/report.json    (parallellt, 20 workers)
index.html          --> visar report.json   (vanilla JS, ingen build)
```

## Filer

- `fetch_kbr.py` - paginerar `https://api.svenskakyrkan.se/kbr/api/byggnader?kyrka=true`,
  hämtar `id, namn, identitetRAA, stift, agandeEnhet, koordinater, nuvarandeAnvandning`.
- `check_ksamsok.py` - ThreadPoolExecutor mot `https://kulturarvsdata.se/raa/bbr/{id}`
  med `Accept: application/json`. Plockar ut `ns5:itemLabel` från entiteten
  med matchande `@id`. Klassificerar via `difflib.SequenceMatcher` med
  tröskel 0.80.
- `index.html` - sammanfattning + filterbara tabeller + dubblettlista.

## Designbeslut

- **Inga externa Python-deps** - bara stdlib. Pipeline ska fungera utan
  uv-installation av paket.
- **Normalisering före likhetsjämförelse:** uppercase, `S:T -> SANKT`,
  ` OCH -> & `, ta bort specialtecken. Räcker för de svenska namn-
  varianter som faktiskt förekommer.
- **Tröskel 0.80** valdes efter spotcheck - lägre gav falska matchar
  ("Bitterna kyrka" vs "Uthus" är 0.10, men "Vårfrukyrkan i Brännkyrka"
  vs "FRUÄNGENS KYRKA, VÅRFRUKYRKAN" är 0.34 och fortfarande tydlig
  mismatch).
- **20 parallella workers** mot K-samsök. Kom upp i ~275 req/s utan
  rate-limiting från servern. Sänk om RAÄ klagar.

## Kända status-buckets

| Status | Vad det betyder |
|---|---|
| `match` | Namnen stämmer överens efter normalisering. |
| `mismatch` | BBR-objektet finns men namnet skiljer sig. Kan vara felmappning **eller** legitim namnvariant. Granska. |
| `not_found` | HTTP 404 - BBR-id existerar inte. |
| `error` | Typiskt HTTP 410 Gone - BBR-objekt borttaget i RAÄ men ligger kvar i KBR. |
| `missing_id` | KBR-kyrkan har inget `identitetRAA` alls (348 stycken 2026-05-13). |

## Att utforska härnäst

- **Koordinatjämförelse:** plocka geometri från BBR (via `bbrb`-undernivå
  eller `lamning`) och korrelera mot KBR:s `xKoordinat`/`yKoordinat`
  (SWEREF99TM). Identifierar fler datafel än bara namn-mismatch. Se
  `_todo.md` punkt 8b.
- **Hitta troliga matchningar för `missing_id`-fallet** via K-samsöks
  `search?query=text=` + namn-likhet + geo-närhet.
- **Berika med foton:** för match-fallen kan `isVisualizedBy`-relationer
  hämtas och miniatyrer länkas in i `kbr-tidslinje/` och liknande.

## Beroenden

Inga utöver Python 3.12 stdlib och `scripts/serve.py` (utanför projektet).
