# PDF-bokhylla

Detta pilotprojekt äger bara Pages-integrationen.

- Produktkod, PDF-extraktion, frontend och läsare ändras i `Armandur/bokhylla`.
- `config.json` pinnar alltid en fullständig bokhylla-commit.
- Ändra inte pinnen utan att först verifiera en full export av alla tre grupper.
- Lägg aldrig OData-nyckeln eller exporterade PDF-filer i git.
- Ett nytt saknat dokument ska utredas. Lägg det inte direkt i tillåtelselistan.
- Håll samma-origin-sökvägar relativa. Ingen CORS-proxy eller FastAPI-server
  ska krävas efter publicering.
