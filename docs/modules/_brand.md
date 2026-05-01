# Grafisk profil

Källa: https://www.svenskakyrkan.se/grafiskprofil + sektionssidor.
Fullständig manual (PDF, 145 sidor):
https://www.svenskakyrkan.se/filer/2396339/240422_SvKy_Manual_Final.pdf

Detta är en sammanfattning för snabbt uppslag vid bygge av frontend-vyer
(signage, widgets, mini-appar) som ska vara grafiskt konsistenta med
Svenska kyrkan. Använd den fullständiga manualen för formellt arbete.

## Färgpalett

### Grundfärger

| Färg | HEX | RGB | NCS |
|---|---|---|---|
| Beige | `#FFEBE1` | 255 235 225 | S 1005-Y30R |
| Svart | `#000000` | 0 0 0 | - |

**Regel:** Svart används **endast för typografi**, aldrig i grafiska
former eller illustrationer.

### Sekundära färger

| Färg | HEX | RGB |
|---|---|---|
| Guld | `#BC8E4C` | 188 142 76 |
| Rosa | `#FFC3AA` | 255 195 170 |
| Orange | `#FF785A` | 255 120 90 |
| Vinröd | `#7D0037` | 125 0 55 |
| Ljuslila | `#CDC3FF` | 205 195 255 |
| Lila | `#9B87FF` | 155 135 255 |
| Mörklila | `#412B72` | 65 43 114 |
| Ljusgrön | `#BEE1C8` | 190 225 200 |
| Grön | `#28A88E` | 40 168 142 |
| Mörkgrön | `#00554B` | 0 85 75 |

**Regel:** Blanda **inte** den gröna och lila färgskalan i samma grafik.

### CSS-variabler (ready-to-use)

```css
:root {
  /* Grundfärger */
  --svk-beige:        #FFEBE1;
  --svk-black:        #000000;

  /* Sekundära */
  --svk-gold:         #BC8E4C;
  --svk-pink:         #FFC3AA;
  --svk-orange:       #FF785A;
  --svk-wine:         #7D0037;
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
3. Beige bakgrund (`#FFEBE1`) eller mörkgrön (`#00554B`) för signage
   (hög läsbarhet på distans).
4. Sekundärfärger för status: t.ex. mörkgrön = öppet, vinröd = stängt
   (undvik ljus rosa/lila som är svaga på distans).
5. Logotypen i hörn på signage-vyer (vit på mörk bakgrund).

## TODO

- Ladda ner logotyp-ZIP:en lokalt och lägg i `docs/specs/` eller
  `signage-platser/static/` när vi börjar visa den.
- Verifiera CMYK/PMS för tryck om det blir aktuellt.
- Hämta hela PDF-manualen (145 sidor) för djupare granskning vid behov.
