# Pipedrive — API capability sheet

> **Scope:** Scaleupboard own Pipedrive account (single instance), employee-facing only.
> **Source of truth for:** sales pipeline až do okamžiku, kdy klient přejde ke koučovi.
> **Docs:** https://developers.pipedrive.com/docs/api/v1 (v1) — https://developers.pipedrive.com/docs/api/v2 (v2, novější endpointy)

---

## Autentizace

- **API token (per-user)** — nejjednodušší, vhodné pro single-account SCB ingest.
  - Get z Pipedrive UI: `Settings → Personal preferences → API`.
  - V hlavičce: `?api_token={token}` (query) nebo `x-api-token` header.
- **OAuth 2.0** — pokud bychom někdy umožnili klientům připojit jejich vlastní Pipedrive (per-tenant). Pro MVP nepotřeba.

Token uložit šifrovaně přes `django-cryptography`.

## Rate limits

- **Tier-based (token-based)**: typically 100 req/2s, 10k/day pro starší plány; novější účty: token budget reset každý 2-sekundový bucket.
- Header `x-ratelimit-remaining`.
- Pagination: `limit` (max 500), `start` (offset) nebo `cursor` u v2.

## Klíčové endpointy a co vrací

| Endpoint | Co vrací | Mapping do Sentinex |
| --- | --- | --- |
| `GET /v1/persons` | Kontakty: id, name, email[], phone[], org_id, owner_id, created/updated | → `Person` + `PersonIdentity(pipedrive_person_id)` |
| `GET /v1/organizations` | Firmy: id, name, address, owner, custom fields | → `Organization` + `OrganizationIdentity(pipedrive_org_id)` |
| `GET /v1/deals` | Dealy: id, title, value, currency, status (open/won/lost), stage_id, person_id, org_id, expected_close_date, won_time, lost_time, lost_reason | → `scb_pipedrive_deal` |
| `GET /v1/activities` | Aktivity: id, type (call/meeting/email/task), subject, due_date, done, deal_id, person_id, org_id, note | → `scb_pipedrive_activity` |
| `GET /v1/notes` | Poznámky k dealu/osobě: content (HTML), pinned, user_id | → `scb_pipedrive_note` |
| `GET /v1/stages` | Stages v pipelinech (číselník) | → `scb_pipedrive_stage` (referenční) |
| `GET /v1/pipelines` | Definice pipelinů | → `scb_pipedrive_pipeline` (referenční) |
| `GET /v1/users` | Pipedrive uživatelé (sales tým) | → `Person(person_type=team)` |
| `GET /v1/files` | Soubory připojené k dealu | → odkaz, neukládáme obsah |
| `GET /v1/products` | Produkty / služby v dealech | → `scb_pipedrive_product` |
| `GET /v1/leads` | Leady (pre-deal) | → `scb_pipedrive_lead` |
| `GET /v1/dealFields`, `personFields`, `organizationFields` | **Custom fields** — kritické | viz níže |

### Custom fields

Pipedrive umožňuje vlastní pole na Person/Organization/Deal. Při syncu:
1. Stáhnout `*/fields` → vytvořit registr `scb_pipedrive_custom_field`.
2. V `raw_payload` JSONB zachovat všechny custom values.
3. Pro klíčová custom fields (např. „program", „segment") přidat strukturované sloupce po dohodě s Pavlem/Petrem.

## Webhooks (real-time)

- `POST /v1/webhooks` — registrace.
- Eventy: `added.deal`, `updated.deal`, `deleted.deal`, totéž pro person/organization/activity.
- Doporučeno: **batch sync každých 15 min + webhooks** pro near-real-time deal updates.

## Datový model v Sentinexu (shared schema)

```
scb_pipedrive_deal
├─ id (UUID)
├─ pipedrive_id (int, unique)
├─ organization_id  → identity.Organization (resolved)
├─ person_id        → identity.Person (resolved, primary contact)
├─ pipedrive_org_id (raw, pro debug)
├─ pipedrive_person_id (raw)
├─ owner_user_id    → identity.Person (sales SCB)
├─ title
├─ stage, pipeline
├─ status (open/won/lost)
├─ value, currency
├─ expected_close_date, won_at, lost_at
├─ lost_reason
├─ source_synced_at
├─ source_id  = pipedrive_id
├─ raw_payload (JSONB, retention 90d)
└─ created_in_pipedrive_at, updated_in_pipedrive_at

scb_pipedrive_activity
├─ id, pipedrive_id, deal_id (FK), person_id, organization_id
├─ type, subject, note, due_date, done, done_at
├─ owner_user_id, source_synced_at, raw_payload

scb_pipedrive_note
├─ id, pipedrive_id, deal_id, person_id, organization_id
├─ content (HTML), content_text (stripped, pro embedding)
├─ created_at, updated_at, raw_payload

scb_pipedrive_pipeline / scb_pipedrive_stage / scb_pipedrive_custom_field
├─ číselníky, sync méně často (1×/den)
```

## Identity resolution flow

```
Pipedrive person → PersonRecord(
  source_system=pipedrive,
  email=primary email,
  full_name=name,
  person_id_in_source=pipedrive_id,
  organization_name=org.name (if linked)
) → IdentityResolver
```

Pipedrive organization → `OrganizationRecord` (id, name, optional IČO custom field).

## Sync strategie

- **Init**: full backfill (persons, orgs, deals, activities, notes) — paginated, store `last_synced_id`.
- **Periodic**: každých 15 min `GET /v1/recents?since_timestamp=...` pro inkrement.
- **Webhooks**: deal updates real-time pro Slack briefing.
- **Číselníky** (stages, pipelines, custom fields): 1×/den.

## Otevřené body

- Které custom fields Pipedrive mám zapojit jako strukturované sloupce (po workshopu s Petrem)?
- Mapování stage → fáze customer journey (sales → onboarding → coaching) — kdo definuje?
- Notes obsahují HTML — strip + embed jen plain text.
