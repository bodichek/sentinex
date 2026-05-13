# Merk.cz — API capability sheet

> **Scope:** Scaleupboard own Merk subscription, employee-facing only (sales/coach lookup).
> **Source of truth for:** externí firemní data o prospektech a klientech (CZ/SK trh).
> **Provider:** Imper / Merk.cz (4M+ subjektů CZ+SK, denní update).
> **Docs:** https://api.merk.cz/docs/ (API klíč v účtu Merk).

---

## Autentizace

- **API klíč** — získání v Merk účtu po objednání API přístupu.
- Header: typicky `Authorization: ApiKey {key}` (⚠️ ověř v dokumentaci).
- Možnost free test API klíče (omezený rozsah).

## Rate limits

⚠️ Nezveřejněno na public stránce. Typicky se u Merk setkáváme s:
- Per-second a per-minute limity (např. 5 req/s, 300/min).
- Batch endpoint umožňuje **až 500 IČOs v 1 requestu** → výrazně šetří limity při hromadném enrichmentu.
- Retry s exponential backoff.

## Klíčové endpointy

| Endpoint (typický) | Co vrací | Účel |
| --- | --- | --- |
| `GET /subjects/{ico}` | Detail firmy podle IČO | hlavní lookup |
| `POST /subjects/batch` | Batch lookup, až 500 IČOs | enrichment existujících klientů |
| `GET /subjects/suggest?query=...` | Autocomplete podle názvu/emailu | sales pre-meeting research |
| `GET /subjects/{ico}/financials` | Finanční výkazy (rozvaha, P&L, ratios) | finanční profil |
| `GET /subjects/{ico}/indicators` | EBIT, EBITDA, ROA, likvidita, trendy | rychlý finanční scoring |
| `GET /subjects/{ico}/contacts` | Ověřené kontakty (telefon, email, osoby) | sales kontaktní lišta |
| `GET /subjects/{ico}/relations` | Vazby na jiné subjekty (vlastníci, dceřinky, propojení) | risk + ownership analýza |
| `GET /subjects/{ico}/officers` | Jednatelé / statutární orgány | KYC, decision makers |
| `GET /subjects/{ico}/public-contracts` | Veřejné zakázky | indikátor velikosti / zdrojů |
| `GET /subjects/{ico}/subsidies` | Dotace | dodatečné finanční signály |
| `GET /changes?since={date}` | Změny v rejstříku od data | průběžný monitoring klientů |
| Iframe embed | Profil firmy / osoby jako embed | UI integrace v BR |

⚠️ Konkrétní paths podle `api.merk.cz/docs` — bude ověřeno při implementaci.

## Co konkrétně Merk umí navíc oproti ARES

| Funkce | ARES | Merk |
| --- | --- | --- |
| IČO/DIČ základ | ✅ | ✅ |
| Adresa, statutární orgány | ✅ | ✅ |
| **Obrat, zisk historicky** | ❌ | ✅ |
| **Finanční výkazy strukturované** | ❌ | ✅ |
| **Finanční indikátory (EBIT, ratios)** | ❌ | ✅ |
| **Risk/credit scoring** | ❌ | ✅ |
| **Ověřené kontakty (telefon, email)** | ❌ | ✅ |
| **Vazby a vlastnické struktury** | částečně | ✅ rich graf |
| **Veřejné zakázky** | částečně | ✅ |
| **Dotace** | ❌ | ✅ |
| **Daily updates + change tracking** | ❌ | ✅ |
| **Batch lookup (500 IČO)** | ❌ | ✅ |

→ Merk je **enrichment** + **monitoring** + **risk** layer nad ARES.

## Datový model

```
scb_merk_company  (cache + enrichment store, shared schema)
├─ id (UUID)
├─ ico (unique)
├─ dic
├─ organization_id  → identity.Organization (linked)
├─ name, legal_form
├─ address (JSONB: street, city, zip, country)
├─ registration_date
├─ status (active / liquidation / bankrupt / dissolved)
├─ nace_codes (array, CZ-NACE klasifikace)
├─ employee_count_range (e.g. "10-49")
├─ turnover_range, last_known_turnover, turnover_year
├─ profit_last, profit_year
├─ rating (Merk risk skóre)
├─ rating_breakdown (JSONB)
├─ contacts_summary (JSONB: phones, emails, persons)
├─ website
├─ source_synced_at
├─ source_id = ico
└─ raw_payload (JSONB)

scb_merk_financials
├─ company_id (FK)
├─ year, period_type (annual)
├─ revenue, ebit, ebitda, net_income, total_assets, equity, debt
├─ ratios (JSONB: roa, roe, current_ratio, debt_to_equity, …)
├─ filed_at, source
├─ source_synced_at, raw_payload

scb_merk_officer
├─ company_id, person_id (FK identity.Person, resolved)
├─ role (jednatel, statutar, prokurista)
├─ valid_from, valid_to
└─ raw_payload

scb_merk_relation
├─ from_company_id, to_company_id
├─ relation_type (vlastník, dceřinka, propojení)
├─ share_percent
├─ valid_from, valid_to
└─ raw_payload

scb_merk_public_contract
├─ company_id, contract_id, contracting_authority
├─ value, awarded_at, subject
└─ raw_payload

scb_merk_subsidy
├─ company_id, subsidy_program, amount, awarded_at
└─ raw_payload
```

## Identity resolution

```
Merk company → OrganizationRecord(
  source_system=merk,
  name=company.name,
  ico=company.ico,
  dic=company.dic,
  id_in_source=company.ico,  # IČO je v Merku primární klíč
) → IdentityResolver
```

IČO je tvrdý identifikátor — Merk slouží jako **autoritativní zdroj IČO/DIČ páru** pro identity resolver. Když FAPI customer nemá DIČ, Merk lookup ho doplní.

Officers (jednatelé) → `PersonRecord` + `PersonOrganizationRole(role=ceo|board)`.

## Sync strategie

### Trigger-based (ne periodic batch)
Merk je **lookup-on-demand**, ne kontinuální stream:

1. **Při registraci nového klienta** (z Pipedrive/FAPI s IČO) → trigger `merk.enrich(ico)` → uloží do `scb_merk_company` + financials + officers.
2. **Před obchodní schůzkou** (sales workflow Krok 1) → automatický lookup + AI profil prospekta.
3. **Periodic refresh**: 1×/měsíc re-pull pro aktivní klienty (financials se updatují s ročním zpožděním, contacts mohou aktualizovat průběžně).
4. **Change tracking**: 1×/týden `GET /changes?since={last}` pro klienty SCB → flag pro Senior kouče (`klient X změnil sídlo / přidal nového jednatele / má novou exekuci`).

## Use cases pro AI a sales

- **Pre-meeting brief**: sales otevře "Nový prospekt" → Sentinex vytáhne Merk profil → AI shrne (velikost, obor, finanční zdraví, kdo rozhoduje).
- **Risk flag**: faktura po splatnosti + Merk rating zhoršený → urgent alert kouči.
- **Decision maker discovery**: "Kdo je CEO firmy X?" → Merk officers + cross-check s Pipedrive contacts.
- **Cross-client patterns**: "Které z našich klientů mají dceřinky?" → graph dotazy přes `scb_merk_relation`.

## Embedding & graph

- Merk popisné texty (NACE, business description) → embeddings pro semantic search.
- Graphiti nodes: Organization, Officer, RelatedCompany; hrany `OWNS`, `HAS_OFFICER`, `RECEIVED_SUBSIDY`.

## Otevřené body

- ⚠️ **Přesné URL endpointů a auth header** ověřit z `api.merk.cz/docs/` po přihlášení do Merk účtu SCB.
- Plán Merk SCB má — jaký je limit batch volání / měsíc?
- Webhooks Merk nenabízí (zatím) → polling change tracker stačí.
- Které extra fieldy (`>100`) chceme strukturované a které zůstanou jen v `raw_payload`?
