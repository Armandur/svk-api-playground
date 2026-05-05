# ls-visualize TODO

Idéer på fler diagram och kartlager. Sorterad i prioordning - högst prio
först. `[KLAR]`-markerade är implementerade.

## Karteffekter

- `[KLAR]` **5. Cirklar proportionella mot antal konton** ovanpå
  polygonerna. En `L.circle` per enhets centroid, radius som
  `sqrt(konton) * 1500m`. Kombinerar "var" och "hur mycket" på samma
  vy. Toggle "Storlekscirklar" i Lager-panelen, default avstängd.
  Skalan är absolut - en enhet med 200 konton har samma cirkel
  oavsett stift.

- **6. Stiftshov-aggregation vid utzoom**
  Vid utzoomad nivå byts enhetspolygoner mot en cirkel per stift -
  storlek = totala konton, färg = anslutningsgrad. Vid inzoom återgår
  till nuvarande vy. Mest kostsam att implementera men ger renaste
  helhetsbild.

- **7. Choropleth på "anslutningsgrad per stift"**
  Toggle som färgar stiften själva (inte enheterna) baserat på % anslutna
  konton. Bra för helhetsbild.

- **8. Hover-popup med mini-stapel**
  När man svävar över en enhet: visa stiftets fördelning Ja/Nej + var
  enheten ligger storleksmässigt jämfört med stiftets medel.

## Diagram och paneler

- `[KLAR]` **1. Stapeldiagram över *konton* per stift, staplat Ja/Nej**
  Inline-bar i Per stift-tabellen som visar % anslutna konton.

- `[KLAR]` **2. Top-10 största ej-anslutna enheter**
  Egen flik i statspanelen.

- `[KLAR]` **3. Donut: andel anslutna enheter vs andel anslutna konton**
  Två donuts sida vid sida i Översikt-fliken.

- `[KLAR]` **4. Histogram: enhetsstorlek (konton)**
  Egen flik i statspanelen, staplat Ja/Nej per storleksintervall.

## Filter och fokus

- **9. Storleksfilter**
  Slider eller dropdown - visa bara enheter med >N konton.

- **10. Stift-fokus**
  Klicka på ett stift för att zooma + visa bara det stiftets enheter.

## Datalager

- **11. Tidslinje över anslutningar**
  Kräver historisk data om när enheterna anslöt - finns inte i
  CSV:n idag. Skulle kräva annan datakälla.

- **12. Korrelation med andra datapunkter**
  T.ex. mot ekonomiska_enheter-API:t (storlek, antal anställda) eller
  KBR (antal byggnader). Bara meningsfullt om vi vill driva en specifik
  hypotes.
