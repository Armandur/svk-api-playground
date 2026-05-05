# Strategi för Rewrite: kbr-kvalitet (Gemini)

Eftersom detta är ett privat projekt utan externa beroenden eller produktionskrav som hindrar stora ingrepp, rekommenderar jag en **fullständig rewrite** i en separat branch. Det nuvarande scriptet har tjänat sitt syfte som prototyp, men arkitekturen begränsar framtida utveckling.

## 1. Mål med rewrite
- **Total separation:** Fetch, Matchning, Kvalitetsanalys och UI ska vara helt oberoende moduler.
- **Developer Experience (DX):** Snabb iteration via aggressiv caching. Inget mer väntande på Overpass-queries under utveckling.
- **Hög precision:** Gå från "bästa gissning" till "ID-säkrad matchning" där det är möjligt.
- **Modern UI-stack:** Dela upp monolit-HTML:en i en renodlad frontend-app (vanilla JS modules + CSS).

---

## 2. Ny Arkitektur

### Fas 1: Data Ingestion & Caching (The "Loader")
Bryt ut `build_report.py` till en modulär loader som skriver rådata till `data/raw/`.
- Varje källa (KBR, Platser, OSM, BV) får en egen fetcher.
- Automatisk TTL-hantering (t.ex. KBR cachas 24h, OSM 6h).
- **Nyhet:** Implementera en `UnitMapper` som hämtar LKF -> EnhetsID-mappningar en gång för alla.

### Fas 2: Analysis & Matching Engine (The "Processor")
En ren Python-motor som jobbar enbart mot `data/raw/`.
- **Matchnings-pipeline:**
  1. Strikt ID-matchning (via LKF/EnhetsID).
  2. Namn-matchning inom samma stift/enhet.
  3. Geografisk fallback (närmaste granne).
- **Kvalitets-plugins:** Varje kvalitetskontroll (datum, koordinater, etc.) blir en egen funktion/klass som returnerar standardiserade "findings". Detta gör det extremt lätt att lägga till nya kontroller utan att röra huvudloopen.

### Fas 3: Frontend (The "Viewer")
Dra nytta av att vi inte behöver en bundler:
- `index.html`: Bara ett skal.
- `src/api.js`: Hanterar laddning av JSON-filer.
- `src/map.js`: Leaflet-logik och lagerhantering.
- `src/table.js`: Reaktiv tabell-rendering (sortering, sökning).
- `src/state.js`: Globalt filter-tillstånd (Stift, Typ, Tröskel) som synkas med URL-hash.

---

## 3. Bold Moves (Rewrite-specifikt)

1.  **Skippa report.csv som standard:** Fokusera på att göra JSON-outputen så rik att CSV-exporten kan genereras on-the-fly i webbläsaren vid behov.
2.  **Inför `primary_source` genomgående:** Inget mer gissande i UI:t. Varje objekt i `report.json` deklarerar explicit vilken källa som äger koordinaten.
3.  **LKF-first matchning:** Gör LKF-mappningen till ett obligatoriskt steg. Utan LKF-matchning flaggas träffen som "Low Confidence".
4.  **Krematorium-fix:** Bryt ut krematorier till en egen förstaklass-typ med egen matchningslogik mot OSM `amenity=crematorium`.

---

## 4. Implementationsplan (Branch: `feature/rewrite`)

1.  **Skeleton:** Sätt upp den nya filstrukturen (`loaders/`, `processors/`, `ui/src/`).
2.  **Caching-lager:** Skriv `core/cache.py` som hanterar filbaserad lagring av API-svar.
3.  **LKF-Mappning:** Bygg bryggan mellan KBR och Platser-API:et.
4.  **UI-migration:** Flytta logiken från `index.html` till ES-moduler bit för bit.
5.  **Quality-port:** Portfölj över de 20+ testerna till det nya plugin-formatet.

---

## Slutsats
Den nuvarande monoliten är en "black box" som är svår att testa och underhålla. Genom en rewrite i en separat branch kan vi bygga ett verktyg som inte bara hittar fel i data, utan som också är arkitektoniskt "rätt" och roligt att bygga vidare på. Fokus ligger på **hastighet i utveckling** och **precision i matchning**.
