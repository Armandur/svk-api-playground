# platser-edit-app

Mini-app för att redigera öppettider på en plats utan att gå via
Content Studio (SVK:s CMS / "platsadministrationen"). Tänkt för
icke-kommunikatörer som vaktmästare, kyrkvärdar - en plats per
session, basic veckoschema-editor.

## Stack

- Vanilla HTML/CSS/JS, ingen bundler.
- Hämtar och skickar via dev-serverns generic SVK-proxy
  (`/api/platser/...`) - se `scripts/serve.py`. APIKEY_PROD läses
  från `.env` på server-sidan, exponeras aldrig i klient-koden.
- Brand: SVK:s grafiska profil (beige + vinröd, DM Sans + Spectral).

## Sökflöde

1. Användaren skriver namn (plats eller församling) i sökrutan.
2. Klient anropar `GET /api/platser/place?q=<text>&limit=20` -
   fritextsökning på platsens namn, ägare, adress m.fl.
3. Resultaten listas med `name` + `owner.name` - klickbara.
4. Klick -> `GET /api/platser/place/{id}` - laddar full plats.

**Senare utbyggnad:** filtrera på församling specifikt via UnitAPI
(`/api/units/...`) eller `?owner_id=` när man vill smalna ner till en
viss enhet. För MVP räcker fritext.

## Editor-läge

När en plats är vald:

- Visar plats-info: namn, ägare, slug, plats-id (UUID).
- Period-väljare om det finns flera (säsongsperioder). MVP redigerar
  bara en period åt gången.
- Veckoschema: 7 rader (Mån-Sön) med en eller flera tids-intervall
  per dag. `+`-knapp lägger till nytt intervall, `×` tar bort.
- "Spara"-knapp skickar `PATCH /api/platser/place/{id}` med:
  ```json
  {
    "updatedBy": "<din identitet>",
    "openHours": { "periods": [...] }
  }
  ```
- Förväntat svar: `204 No Content` + Location-header.

## Datakontrakt

Se [`docs/modules/PLATSER.md`](../docs/modules/PLATSER.md) för full
modell. Centralt:

```jsonc
{
  "openHours": {
    "info": "fritextkommentar",
    "periods": [
      {
        "validFrom": "2022-03-17",   // ISO date eller saknas
        "validTo": null,             // null/saknas = "tills vidare"
        "days": {
          "mo": [{"from": "08:00", "to": "16:00"}],
          "tu": [], ...              // tom array = stängt den dagen
        }
      }
    ]
  }
}
```

## Skriv-regler (från Platser-API:t)

- `updatedBy` är **obligatoriskt** vid uppdatering, får aldrig vara null.
- Hela `openHours.periods`-listan ersätts (inga merges) - skicka
  fullständig periods-array.
- Andra fält som inte ska ändras: skicka inte med dem (PATCH ignorerar
  utelämnade fält).
- 404 om plats inte finns; 403 om vår nyckel saknar skrivbehörighet.

## TODO

- Stöd för `validFrom`/`validTo` i editorn (säsongsperioder).
- Lägg till/ta bort hela perioder.
- Editera `openHours.info` (fritextkommentar).
- Användare-namn-fält för `updatedBy` (idag hårdkodat).
- Bekräftelse-modal innan PATCH skickas.
- Optimistic UI med rollback vid fel.
- Auth - just nu kommer alla med tillgång till dev-servern kunna
  skriva. För riktigt bruk behöver vi någon form av magic-link-auth
  eller liknande.