# Felaktiga platser i Bönewebben

Lista över platser i `be.svenskakyrkan.se/api` med felaktiga eller
saknade koordinater. Påverkar inte ljuständningen i sig, men gör
att ljus från dessa platser inte hamnar på rätt ställe på den
geografiska kartan.

## Metod

Två typiska fel observerades i `position_lat` / `position_long`:

1. **Saknade koordinater** - båda fält 0, eller bara longituden 0.
2. **Ihopkopplade fel** - lat och lng är swappade (t.ex. lat=13.8
   som är omöjligt i Sverige medan lng=58.4 är ett rimligt latitudvärde).

För platser med swappade värden räckte det att byta plats på dem
för att få korrekt position. För platser med 0-värden eller
ungefärliga positioner fastställdes rätt position via Google Maps.

## Korrigerbara (7 platser)

Felet och rätt position fastställd. Fältet `Föreslagen position`
kan användas direkt vid rättning.

### Umeå sjukhus

- **id:** `3529`  ·  **slug:** `umeaaaa_sjukhus`
- **Beskrivning i API:** Umeå sjukhus i Umeå
- **Fel:** saknad position
- **Nuvarande API-position:** `position_lat=0.0`, `position_long=0.0`
- **Föreslagen position:** `position_lat=63.81759925185444`, `position_long=20.298219709644773`
- **Verifierad:** [Google Maps](https://www.google.com/maps?q=63.81759925185444,20.298219709644773)
- **Kommentar:** API anger (0, 0). Korrekt position fastställd via Google Maps mot Umeå Norrlands universitetssjukhus.

### Terra Nova-kyrkan

- **id:** `3596`  ·  **slug:** `terra_nova-kyrkan`
- **Beskrivning i API:** Terra Nova-kyrkan, Visby domkyrkoförsamling. Samarbetskyrka med EFS.
- **Fel:** saknad position
- **Nuvarande API-position:** `position_lat=0.0`, `position_long=0.0`
- **Föreslagen position:** `position_lat=57.61330656398801`, `position_long=18.31114518147621`
- **Verifierad:** [Google Maps](https://www.google.com/maps?q=57.61330656398801,18.31114518147621)
- **Kommentar:** API anger (0, 0). Korrekt position via Google Maps - Terra Nova-kyrkan i Visby.

### Karesuando gamla kyrkogård

- **id:** `3893`  ·  **slug:** `karesuando_gamla_kyrkogaaaard`
- **Beskrivning i API:** Karesuando gamla kyrkogård i Kiruna
- **Fel:** ungefärlig position
- **Nuvarande API-position:** `position_lat=68.461`, `position_long=22.441`
- **Föreslagen position:** `position_lat=68.45307210516269`, `position_long=22.443367825027554`
- **Verifierad:** [Google Maps](https://www.google.com/maps?q=68.45307210516269,22.443367825027554)
- **Kommentar:** API-positionen ligger ~1 km från korrekt plats. Korrigerad via Google Maps.

### Forsa kyrkogård

- **id:** `3756`  ·  **slug:** `forsa_kyrkogaaaard`
- **Beskrivning i API:** Forsa kyrkogård i Hudiksvall.
- **Fel:** lat/lng ihopkopplade fel
- **Nuvarande API-position:** `position_lat=16.9397`, `position_long=61.7364`
- **Föreslagen position:** `position_lat=61.73509569298956`, `position_long=16.937440530422727`
- **Verifierad:** [Google Maps](https://www.google.com/maps?q=61.73509569298956,16.937440530422727)
- **Kommentar:** position_lat och position_long är swappade. Efter swap och Google Maps-kontroll: Hudiksvall-trakten.

### Hosjö kyrkogård

- **id:** `3840`  ·  **slug:** `hosjaaoe_kyrkogaaaard`
- **Beskrivning i API:** Hosjö kyrkogård i Falun
- **Fel:** lat/lng ihopkopplade fel
- **Nuvarande API-position:** `position_lat=15.7606`, `position_long=60.5935`
- **Föreslagen position:** `position_lat=60.592306198034855`, `position_long=15.76170416532879`
- **Verifierad:** [Google Maps](https://www.google.com/maps?q=60.592306198034855,15.76170416532879)
- **Kommentar:** position_lat och position_long är swappade. Efter swap och Google Maps-kontroll: Falun (Hosjö).

### S:t Lukas kyrka

- **id:** `3645`  ·  **slug:** `st_lukas_kyrka_i_skaaoevde`
- **Beskrivning i API:** S:t Lukas kyrka i Skövde
- **Fel:** lat/lng ihopkopplade fel
- **Nuvarande API-position:** `position_lat=13.8227`, `position_long=58.4042`
- **Föreslagen position:** `position_lat=58.40421375984256`, `position_long=13.822435995894448`
- **Verifierad:** [Google Maps](https://www.google.com/maps?q=58.40421375984256,13.822435995894448)
- **Kommentar:** position_lat och position_long är swappade. Efter swap och Google Maps-kontroll: Skövde.

### S:ta Birgittas kapell

- **id:** `3646`  ·  **slug:** `sta_birgittas_kapell_i_skaaoevde`
- **Beskrivning i API:** S:ta Birgittas kapell i Skövde
- **Fel:** lat/lng ihopkopplade fel
- **Nuvarande API-position:** `position_lat=13.8356`, `position_long=58.397`
- **Föreslagen position:** `position_lat=58.397`, `position_long=13.8356`
- **Verifierad:** [Google Maps](https://www.google.com/maps?q=58.397,13.8356)
- **Kommentar:** position_lat och position_long är swappade. Efter swap och Google Maps-kontroll: Skövde.

## Otillräckligt underlag (2 platser)

Behöver disambigueras eller kompletteras av SVK - vi har inte
tillräckligt med information för att fastställa rätt position.

### Slottskyrkogården

- **id:** `3534`  ·  **slug:** `slottskyrkogaaaarden`
- **Beskrivning i API:** Slottskyrkogården i Jönköping
- **Fel:** saknad position
- **Nuvarande API-position:** `position_lat=0.0`, `position_long=0.0`
- **Kommentar:** API anger (0, 0). Namnet 'Slottskyrkogården' finns på flera platser i Sverige (Stockholm, Mariefred, Bohus-Malmön m.fl.) - kan inte disambigueras utan ytterligare information.

### Ansgarskyrkan

- **id:** `1224`  ·  **slug:** `ansgarskyrkan`
- **Beskrivning i API:** Ansgarskyrkan i Eskilstuna
- **Fel:** saknad longitud
- **Nuvarande API-position:** `position_lat=58.4154`, `position_long=0.0`
- **Kommentar:** API anger lng=0 (lat verkar finnas men lng saknas). Ansgarskyrkan finns i flera städer (Stockholm, Lidköping, Vällingby, Jönköping).
