# Ersatta tjänster

Listas i portalkatalogen men ska inte användas för nya integrationer.

## Calendar Search

- **Status:** Deprecated.
- **Ersättare:** [CalendarAPI](#CALENDARAPI). Funktionellt även täckt av
  [CHURCHCALENDAR](#CHURCHCALENDAR) (`webapi/api-v2/churchcalendar`)
  för kyrkoåret-relaterad data.
- **Portal-länkar:**
  - Prod: `https://api.svenskakyrkan.se/tjanster/07f41769-2a61-47c5-afed-d1d995a6a5e4`
  - Test: `https://api-t.svenskakyrkan.se/tjanster/07f41769-2a61-47c5-afed-d1d995a6a5e4`

## Platser v3

- **Status:** Fryst, planerad nedstängning.
- **Ersättare:** Platser v4 - se [PLATSER](#PLATSER).

## calendarserviceapi (test-portal)

Test-portalen listar separata "Kyrkoåret" och "Kyrkoårets bibeltexter"
som pekar på `api-t.svenskakyrkan.se/calendarserviceapi/v1/...`.
Servrarna **svarar inte över publika nätverk** (kräver kyrknätet).

- **Doc-URL:er (ej publikt nåbara):**
  - `https://api-t.svenskakyrkan.se/calendarserviceapi/v1/churchyear/doc`
  - `https://api-t.svenskakyrkan.se/calendarserviceapi/v1/calendar/doc`
  - `https://api-t.svenskakyrkan.se/externwebb/calendar/doc`
- **Publik ersättare:** Använd istället
  [CHURCHCALENDAR](#CHURCHCALENDAR) som täcker samma data.

## Vad som inte är dokumenterat

Vissa tjänster i test-portalen syns inte i prod-portalen. Per 2026-04-30:

- **Enhetsinformation** - bara test-portal, men prod-instansen finns och
  fungerar (se [ENHETSINFORMATION](#ENHETSINFORMATION)).
- **CalendarAPI** - bara test-portal i SVK:s katalog, men ligger på
  Azure APIM-prod (se [CALENDARAPI](#CALENDARAPI)).

Det här är troligen en synlighetsfråga i portalen; tjänsterna är
publicerade men inte exponerade i prod-katalogen.
