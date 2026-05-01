# kyrkoaret-widget

Widget som visar dagens högtid i kyrkoåret med liturgisk färg, beskrivning,
kyrkoårsdel och dagens bibeltexter. Embed:as i församlingars hemsidor
eller används som sidoyta på en signage-skärm.

## Stack

- Vanilla HTML/CSS/JS, ingen bundler, **inga byggsteg**.
- Hämtar direkt från `https://www.svenskakyrkan.se/webapi/api-v2/churchcalendar`
  via klient-side `fetch()`. apiKey:n
  `139ff33b-4451-4f0f-b397-1f4ec9307a87` är **publik klientside-nyckel**
  (samma som webbplatsens egen JS använder), så ingen server-proxy
  behövs.
- En enda `index.html` med inline CSS och JS.
- Brand: SVK:s grafiska profil (beige bakgrund, vinröd accent,
  DM Sans + Spectral). Liturgiska färger visas som en separat
  swatch - inte mappade till brand-paletten eftersom de har egen
  betydelse.

## Datalogik

API:t returnerar 66 entries per kyrkoår, en per "feast-dag" (söndagar +
storhögtider). Vanliga vardagar har **ingen entry**. Strategi:

1. Hitta entry vars `startDate <= idag <= endDate` (dagens exakta högtid).
2. Annars: hitta första entry vars `startDate > idag` (närmaste kommande
   högtid). Visa då tydligt att det är "i förväg".
3. Visa alltid kyrkoårsdel (`churchYearPart`) - den gäller även mellan
   söndagar.

## Liturgisk färg-mappning

`liturgicalColor`-värden (från [CHURCHCALENDAR](../docs/modules/CHURCHCALENDAR.md))
mappas till en visuell swatch. Använd traditionella liturgiska toner,
**inte** SVK:s grafiska profil:

| API-värde | Visuell färg |
|---|---|
| `White` | vit/grädde |
| `Violet` | klassisk lila |
| `Red` | klassisk röd |
| `Green` | klassisk grön |
| `Black` | svart |
| `Blue` | blå |
| `VioletOrBlue` | lila (med blå-not i tooltip) |
| `GreenOrBlue` | grön |
| `GreenOrWhite` | grön |

`liturgicalColorDisplay` har den läsbara svenska beskrivningen
(t.ex. "Vit - byte till violett/blå efter kl 18") - visa som tooltip
eller hjälptext.

## Kör lokalt

```bash
# Servern (från repo-roten) listar widgeten på startsidan
./start.sh
# -> http://localhost:8088/kyrkoaret-widget/
```

Inga env-vars behövs - apiKey:n ligger inline i index.html.

## TODO

- Visa flera dagar framåt (en mini-månadsvy?).
- Embed-läge: `?embed=1` triggar minimalistisk variant utan rubriker.
- Hantera laddningsfel snyggt (offline / API down).
- Cache i `localStorage` så widgeten visar något även när nätet är nere.
- Variant som visar veckans gudstjänster när vi har en CalendarAPI-key
  och kan korsreferensa events mot dagens högtid.