# Konektory — přehled

Tato složka obsahuje **capability sheety** pro každý aktivně připravovaný konektor.
Každý dokument popisuje API daného systému: auth, endpointy, mapping do Sentinex modelů,
identity resolution flow, sync strategii a otevřené body.

## Priorita 1 — aktivně dokumentováno

| Konektor | Status dok | Status kódu | Účel |
| --- | --- | --- | --- |
| [Pipedrive](pipedrive.md) | ✅ | scaffolding | Sales pipeline SCB |
| [FAPI](fapi.md) | ✅ ⚠️ ověř | scaffolding | Fakturace SCB → klienti |
| [Slack](slack.md) | ✅ | scaffolding | Interní tým + výstupní zprávy |
| [Google Workspace](google_workspace.md) | ✅ | scaffolding (microsoft365 existuje, Google chybí) | Kalendář, Drive |
| [Merk.cz](merk.md) | ✅ ⚠️ ověř | neexistuje | Externí firemní data CZ/SK |

⚠️ ověř = doplnit detaily z reálného účtu SCB (FAPI dokumentace v účtu, Merk API spec).

## Priorita 2+ — scaffolding existuje, dokumentace přijde později

asana, basecamp, calendly, canva, dropbox, ecomail, hubspot, jira, mailchimp,
microsoft365, notion, raynet, salesforce, smartemailing, trello

## Plánováno, neexistuje

- **Zoom** — přepisy schůzek
- **Symfio** — klientovy finanční reporty
- **ABRA** — alternativa FAPI
- **MGS** — interní firemní data SCB
- **BR web** — firemní web s členskou sekcí

## Společný vzor (před implementací frameworku)

Každý konektor bude implementovat:

1. **Credential storage** (API key / OAuth tokens), šifrovaně přes `django-cryptography`.
2. **Sync state** (`last_synced_at`, `last_cursor`, `error_count`).
3. **Rate limit handling** (per-API limity).
4. **Retry s exponential backoff**.
5. **Provenance fields** na všech sync tabulkách (`source_synced_at`, `source_id`, `raw_payload`).
6. **Identity resolution** (volání `IdentityResolver` před uložením Person/Organization záznamů).
7. **Celery beat task** pro periodický sync.
8. **Admin UI** pro připojení/odpojení a sledování stavu.
9. **Audit logging**.
10. **Per-tenant scope** (kde to dává smysl) — většina konektorů SCB-only.

Tento společný vzor se vykristalizuje v `apps/connectors/_framework/` (TBD).
