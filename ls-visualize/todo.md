# ls-visualize TODO

Idéer på fler diagram och kartlager. Sorterad i prioordning - högst prio
först. De tre översta (markerade `[NU]`) implementeras i denna runda.

## Karteffekter

- `[NU]` **5. Cirklar proportionella mot antal konton** ovanpå
  polygonerna. En `circleMarker` per enhets centroid, radius som
  `sqrt(konton)`. Kombinerar "var" och "hur mycket" på samma vy.

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

- `[NU]` **1. Stapeldiagram över *konton* per stift, staplat Ja/Nej**
  Istället för (eller utöver) "antal enheter" i statspanelen visa
  "antal konton". Då syns att stora pastorat kan ge ett "Nej"
  oproportionerlig tyngd.

- `[NU]` **2. Top-10 största kontolösa enheter**
  Listpanel med de största enheter som *inte* anslutit. Operativt nyttig
  för "vem prata med härnäst".

- **3. Donut: andel anslutna enheter vs andel anslutna konton**
  Två värden sida vid sida. Ofta väldigt olika - det är insikt nr 1.

- **4. Histogram: enhetsstorlek (konton)**
  Färgat per status. Visar om det är systematiskt små eller stora
  enheter som står utanför.

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
