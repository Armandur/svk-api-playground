# Grafisk profil

Källa: https://www.svenskakyrkan.se/grafiskprofil + sektionssidor.
Fullständig manual (PDF, 145 sidor):
https://www.svenskakyrkan.se/filer/2396339/240422_SvKy_Manual_Final.pdf

Detta är en sammanfattning för snabbt uppslag vid bygge av frontend-vyer
(signage, widgets, mini-appar) som ska vara grafiskt konsistenta med
Svenska kyrkan. Använd den fullständiga manualen för formellt arbete.

## Färgpalett

Färgerna delas i tre grupper: **grundfärger**, **primärfärger** och
**sekundärfärger**. Tillsammans med den svarta typografin utgör de
Svenska kyrkans grafiska uttryck.

### Grundfärger

| Färg | HEX | RGB | NCS | PMS C |
|---|---|---|---|---|
| Beige | `#FFEBE1` | 255 235 225 | S 1005-Y30R | 9226 C |
| Svart | `#000000` | 0 0 0 | - | Black 6 C |

**Regler:**
- Svart används **endast för typografi**, aldrig i grafiska former eller
  illustrationer.
- Vid utskrift på lokal skrivare får beige bakgrund ersättas med vit.

### Primärfärger

Dessa tre är **kärnan** i paletten. Minst en primärfärg ska användas
i varje grafiskt uttryck (utöver grundfärgen beige).

| Färg | HEX | RGB | CMYK | PMS C |
|---|---|---|---|---|
| Vinröd | `#7D0037` | 125 0 55 | 0.100.40.55 | 4074 C |
| Orange | `#FF785A` | 255 120 90 | 0.70.70.0 | 1665 C |
| Rosa | `#FFC3AA` | 255 195 170 | 0.40.40.0 | 7520 C |

**Praktik:** vinröd är den dominanta primärfärgen och används
övervägande i merparten av Svenska kyrkans grafik. Använd den som
default-accent / huvudfärg i nya vyer; orange och rosa funkar bättre
som komplement eller i specialkampanjer.

### Sekundärfärger

Komplement som används utöver grundfärger + primärfärger.

| Färg | HEX | RGB | CMYK | PMS C |
|---|---|---|---|---|
| Guld | `#BC8E4C` | 188 142 76 | 20.40.70.25 | 872 C |
| Ljuslila | `#CDC3FF` | 205 195 255 | 33.35.0.0 | 9344 C |
| Lila | `#9B87FF` | 155 135 255 | 63.65.0.0 | 2665 C |
| Mörklila | `#412B72` | 65 43 114 | 80.85.0.35 | 3535 C |
| Ljusgrön | `#BEE1C8` | 190 225 200 | 35.0.35.0 | 9504 C |
| Grön | `#28A88E` | 40 168 142 | 100.10.65.0 | 3278 C |
| Mörkgrön | `#00554B` | 0 85 75 | 100.10.70.50 | 329 C |

### Kombinationsregler

- **Beige + minst en primärfärg** är obligatoriskt i varje
  grafiskt uttryck.
- Med tre eller fyra färgytor får man hämta från sekundärpaletten,
  så länge ovanstående regel hålls.
- **Blanda inte** den gröna och lila skalan i samma grafik.
- Andra färgsystem (NCS, RAL, TCX, Oracal) finns dokumenterade i
  manualen för fysiska kontaktytor (väggar, tyg, vinyl). Använd
  rätt färgsystem per kontaktyta - en CMYK-färg får t.ex. inte
  tryckas på en NCS-färg.

### CSS-variabler (ready-to-use)

```css
:root {
  /* Grundfärger - beige bakgrund + svart typografi */
  --svk-beige:        #FFEBE1;
  --svk-black:        #000000;

  /* Primärfärger - minst en ska alltid användas */
  --svk-wine:         #7D0037;
  --svk-orange:       #FF785A;
  --svk-pink:         #FFC3AA;

  /* Sekundärfärger - komplement */
  --svk-gold:         #BC8E4C;
  --svk-light-purple: #CDC3FF;
  --svk-purple:       #9B87FF;
  --svk-dark-purple:  #412B72;
  --svk-light-green:  #BEE1C8;
  --svk-green:        #28A88E;
  --svk-dark-green:   #00554B;
}
```

## Typografi

Två typsnitt, båda fritt tillgängliga via Google Fonts.

| Typsnitt | Vikter | Användning |
|---|---|---|
| **DM Sans** | Regular, Medium, Bold | Rubriker (Medium), brödtext, ingress, listor (Regular). Bold sparsamt. |
| **Spectral** | Italic, Regular | Accent/emfas (Italic), längre rapporttexter (Regular) |

### Web-fonts

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Spectral:ital,wght@0,400;1,400&display=swap" rel="stylesheet">
```

Fallbacks vid avsaknad: **Arial** (DM Sans) och **Times New Roman Italic**
(Spectral).

### Radavstånd

| Storlek | Line-height |
|---|---|
| Stora rubriker | 93-103% av typstorlek |
| Ingress / små rubriker | 110-120% |
| Brödtext | 120% |

### CSS-snippet

```css
:root {
  --svk-font-sans:   "DM Sans", Arial, sans-serif;
  --svk-font-serif:  "Spectral", "Times New Roman", serif;
}
body { font-family: var(--svk-font-sans); }
h1, h2, h3 { font-family: var(--svk-font-sans); font-weight: 500; line-height: 1.0; }
.lead { font-size: 1.25em; line-height: 1.15; }
em, .accent { font-family: var(--svk-font-serif); font-style: italic; }
```

## Logotyp

- **Form:** sköld med rött kors + guldkrona, ackompanjerat av texten
  "Svenska kyrkan".
- **Symbolik:** röd = Guds kärlek, guld = det eviga ljuset / Guds härlighet.
- **Filer:** ZIP med vektorer
  https://www.svenskakyrkan.se/filer/2396339/Logotyp_2024_svenska.zip

### Färgvarianter

| Variant | Användning |
|---|---|
| Svart | På ljusa bakgrunder |
| Vit | På mörka bakgrunder, foto eller film |
| Enfärgad | Begränsade fall (prägling, små ytor) |

### Friyta och storlek

- Friytan = avståndet mellan de streckade hjälplinjerna runt logotypen
  (cirka 5% av ytans kortaste sida som minimum).
- Tryck-storlekar är specade per pappersformat (A3-A6).
- Digitalt: logotypen ska utgöra en viss procent av ytans bredd
  (varierar per kontext - Instagram story, annonsskärm m.fl.).

## Designprincip

Konceptet kallas **"Sprida hopp"** - inspirerat av kyrkfönstrens
färgade ljus. Färgerna är "varma och dynamiska". Färger, kontrast och
typsnitt är testade att överstiga **WCAG 2 AA**.

## Tillämpning på pilot-projekt

För `signage-platser/`, `kyrkoaret-widget/` m.fl. - använd:

1. CSS-variablerna ovan.
2. DM Sans + Spectral via Google Fonts.
3. Beige bakgrund (`#FFEBE1`) som default-canvas - högsta igenkänning.
4. **Vinröd (`#7D0037`) som dominant accent** - status, knappar,
   rubriker, ikoner. Dominerar i praktiken det grafiska språket.
5. Mörkgrön/grön kan användas som "öppet"-state om en kontrast mot
   vinröd "stängt"-state behövs - men säkerställ att vinröd finns
   med någonstans i vyn (regel: minst en primärfärg).
6. Undvik ljusrosa/ljuslila för status-text på distans, de är svaga.
7. Logotypen i hörn på signage-vyer (svart på beige eller vit på mörk
   bakgrund).

## TODO

- Ladda ner logotyp-ZIP:en lokalt och lägg i `docs/specs/` eller
  `signage-platser/static/` när vi börjar visa den.
- Verifiera CMYK/PMS för tryck om det blir aktuellt.
- Hämta hela PDF-manualen (145 sidor) för djupare granskning vid behov.
