# Sentinex — databázová struktura

> **Verze:** 1.1 — květen 2026 (rozhodnutí potvrzena)
> **Účel:** Návrh DB struktury pro propojení dat z BR (coaching) + FAPI + Pipedrive + Slack + Trello + dalších systémů přes jednoho klienta.
> **Status:** návrh k odsouhlasení, otevřené otázky na konci.

---

## 1. Dvě úrovně dat

Sentinex pracuje se dvěma logicky oddělenými druhy dat:

### Úroveň 1: Data, která Scaleupboard má O klientech
- **Pipedrive** — sales pipeline, dealy se Scaleupboard
- **FAPI** — faktury, které Scaleupboard vystavuje klientovi
- **Slack** — interní channely Scaleupboard týmu
- **Zoom** — schůzky Scaleupboard kouče s klientem
- **BR** — coaching záznamy, výzvy, SCL/TMF, finanční výkazy klienta
- **Merk** — externí firemní data

Tato data patří Scaleupboardu a jsou o všech klientech. Žijí ve **sdíleném (public) schema**.

### Úroveň 2: Data, která patří KLIENTOVI
- Klientovy vlastní faktury (jejich P&L)
- Klientův Trello / Asana / Jira (jejich projekty)
- Klientův vlastní Slack (jejich tým)
- Klientův vlastní Pipedrive (jejich sales)
- Klientovy Google dokumenty

Tato data patří klientovi a Sentinex k nim přistupuje jen pokud klient připojí svoje účty. Žijí v **per-tenant schema**.

---

## 2. Schema layout

```
PUBLIC SCHEMA (Scaleupboard data + identity registry)
├─ Tenant                    ← klient (firma), 1 řádek = 1 schema
├─ Domain                    ← tenant resolution
├─ User                      ← uživatelé Sentinexu (SCB tým + klientští CEO)
├─ TenantMembership          ← kdo do kterého tenantu patří + role
│
├─ Organization              ← KAŽDÁ firma (klienti SCB, dodavatelé, prospekty…)
├─ Person                    ← KAŽDÁ osoba (CEO klienta, SCB tým, kontakty)
├─ PersonIdentity            ← emaily, slack_id, pipedrive_id, fapi_id, br_user_id
├─ PersonOrganizationRole    ← Person ↔ Organization (CEO, kontakt, atd.)
│
├─ scb_pipedrive_deal        ← Pipedrive deals (Scaleupboard's)
├─ scb_pipedrive_activity
├─ scb_fapi_invoice          ← Faktury vystavené SCB klientům
├─ scb_fapi_payment
├─ scb_slack_workspace       ← Scaleupboard's Slack
├─ scb_slack_channel
├─ scb_slack_message
├─ scb_zoom_meeting          ← SCB kouč × klient
├─ scb_zoom_transcript
├─ scb_merk_company          ← externí data o klientovi
│
├─ br_client_profile         ← (po migraci BR) — coaching profil klienta
├─ br_survey_session         ← SCL / TMF dotazníky
├─ br_business_review        ← zápisy z BR sezení
├─ br_coaching_session       ← publikované 1:1 výstupy
├─ br_client_challenge       ← výzvy (unified)
├─ br_financial_statement    ← klientovy finanční výkazy nahrané do BR
│
├─ agent_run                 ← log každého spuštění agenta
├─ memory_embedding          ← pgvector — společný retrieval index
├─ provenance                ← citation engine — odkazy na zdroje
├─ event                     ← Kafka event log mirror
├─ audit_log                 ← kdo/co/kdy
│
└─ usage_record              ← per-tenant cost tracking

TENANT SCHEMA <client_acme>  (1 schema per klient firma)
├─ acme_trello_board         ← klientova vlastní Trello
├─ acme_trello_card
├─ acme_asana_project        ← klientova vlastní Asana
├─ acme_jira_issue           ← klientova vlastní Jira
├─ acme_slack_workspace      ← klientův vlastní Slack
├─ acme_slack_message
├─ acme_pipedrive_deal       ← klientův vlastní Pipedrive
├─ acme_fapi_invoice         ← klientovy vlastní vystavené faktury
├─ acme_google_doc           ← klientovy Google dokumenty
├─ acme_zoom_transcript      ← klientovy interní porady
└─ acme_memory_embedding     ← per-tenant embeddings (privátní)
```

---

## 3. Klíčová tabulka: provázání všeho přes Person + Organization

Každý záznam z konektoru má FK na **Person** nebo **Organization** (nebo oboje). Tím se data propojí.

### Příklad: FAPI faktura
```
scb_fapi_invoice
├─ id
├─ fapi_id              ← původní ID v FAPI
├─ organization_id      ← FK na Organization (klientova firma)
├─ amount, currency, due_date, paid_at
├─ source_synced_at     ← provenance
└─ raw_payload          ← JSONB, originální FAPI response
```

### Příklad: Pipedrive deal
```
scb_pipedrive_deal
├─ id
├─ pipedrive_id
├─ organization_id      ← FK na Organization
├─ person_id            ← FK na Person (kontakt v Pipedrive)
├─ stage, value, status, won_at
├─ source_synced_at
└─ raw_payload
```

### Příklad: Slack zpráva
```
scb_slack_message
├─ id
├─ channel_id
├─ slack_user_id
├─ person_id            ← FK na Person (resolved přes PersonIdentity)
├─ ts, thread_ts
├─ text, mentioned_person_ids (array)
├─ source_synced_at
└─ raw_payload
```

### Příklad: BR coaching session
```
br_coaching_session
├─ id
├─ person_id            ← FK na Person (klient CEO)
├─ organization_id      ← FK na Organization (klientova firma)
├─ coach_person_id      ← FK na Person (kouč)
├─ session_date
├─ ai_summary, transcript_ref
├─ published_at
└─ source_synced_at
```

**Výsledek:**
- "Vše o klientovi ACME"? → `WHERE organization_id = ACME` napříč tabulkami.
- "Vše o Janu Novákovi"? → `WHERE person_id = JN`.
- Identity resolver zaručí, že je to vždy správně napárované.

---

## 4. Provenance — univerzální citation

### Varianta A: per-tabulka fields (doporučeno)
Každá tabulka má `source_synced_at`, `source_id`, `raw_payload`. Rychlé, jednoduché.

### Varianta B: samostatná provenance tabulka
```
provenance
├─ id
├─ entity_type        ← "fapi_invoice", "pipedrive_deal"…
├─ entity_id          ← FK na konkrétní záznam
├─ source_system      ← "fapi", "pipedrive", "slack"
├─ source_id          ← původní ID
├─ synced_at
├─ confidence         ← 1.0 pro tvrdé zdroje, nižší pro AI-extracted
└─ raw_payload_ref
```

Elegantní, ale náročnější na výkon. **Doporučuju Variant A** pro běžné zdroje + samostatná tabulka jen pro AI-derived facts.

---

## 5. Memory & graph layer

### pgvector embeddings
```
memory_embedding
├─ entity_type, entity_id    ← na co se vztahuje
├─ content_text              ← původní text
├─ embedding (vector)
├─ organization_id, person_id ← scope pro filtraci
└─ created_at, source
```

Použití: "najdi všechno, co se podobá dotazu, scope na Organization X".

### Graphiti / Neo4j
- **Uzly:** Person, Organization, Deal, Invoice, Meeting, Challenge, Document.
- **Hrany:** WORKS_FOR (Person→Organization), SIGNED_DEAL (Person→Deal), MENTIONED_IN (Person→Message), CONNECTED_TO_GOAL (Deal→Goal).
- **Každá hrana** má `valid_from`, `valid_to`, `confidence`, `source`.

Použití: "ukaž celou síť kolem klienta Novák" — vrátí všechny entity v dosahu 2 skoků.

---

## 6. Konkrétní příklad: agent odpovídá "Co víme o klientovi ACME?"

```
1. Resolver: ACME (string) → Organization(id=42)
2. Insight function "client_360(org_id=42)" pošle dotazy:
   ├─ scb_pipedrive_deal WHERE org_id=42        → [deal #100, deal #105]
   ├─ scb_fapi_invoice WHERE org_id=42          → [3 faktury, 1 po splatnosti]
   ├─ br_coaching_session WHERE org_id=42       → [5 sezení, poslední 2026-04-20]
   ├─ br_client_challenge WHERE org_id=42       → [2 aktivní výzvy]
   ├─ scb_slack_message WHERE 42 IN mentioned   → [12 zmínek za 30 dní]
   └─ memory_embedding semantic search "ACME"   → [3 nestrukturované poznámky]
3. Graphiti: subgraph(Organization=42, depth=2)
4. LangGraph agent složí odpověď + cituje každý fact
   (FAPI invoice #INV-2026-042, BR session 2026-04-20…)
```

---

## 7. Rozhodnutí (potvrzená)

| # | Otázka | Rozhodnutí |
| --- | --- | --- |
| 1 | Tenant model | **Každý klient = vlastní schema.** Hard isolation mezi klienty. |
| 2 | Per-klient schema | **Ano, hned.** Nejen pro klientovy připojené účty, ale i pro BR/coaching data. |
| 3 | Provenance | **Per-tabulka fields** (`source_synced_at`, `source_id`, `raw_payload`). |
| 4 | raw_payload JSONB | **Ano**, retention 90 dní. |
| 5 | BR data umístění | **Per-tenant schema.** Důvěrnost 1:1, GDPR drop-schema, klient se přihlašuje a vidí jen své. |

## 7.1 Důsledky a vzorce dotazování

**SCB zaměstnanec přistupuje napříč klienty třemi vzorci:**

**(a) "Otevři klienta X" — nejčastější**
```python
tenant = Tenant.objects.get(organization_id=X)
with schema_context(tenant.schema_name):
    sessions = CoachingSession.objects.filter(person_id=...)
```
Django-tenants natively přepne schema per request. SCB role má povoleno přepínat, klient ne.

**(b) Cross-client reporting**
- Pomalá cesta: loop přes všechny tenanty, `with schema_context(...)`.
- Rychlá cesta: **read-only mirror tabulky v public schema** (`scb_client_summary`, `scb_session_index`) — Celery beat job sype agregace každých 15 min. Reporting běží proti public, ne proti N schématům.

**(c) Hluboký AI dotaz napříč klienty**
Vzácné, většinou nepotřebné (GDPR). Insight function s explicitním scope `tenants=[A, B, C]`, jen pro Senior kouče/Admin, audit log povinný.

## 7.2 Hybrid pro coaching reporting (později)

- 1:1 obsah (přepisy, AI shrnutí, finance) → **per-tenant** (citlivé).
- 1:1 metadata (datum, kouč, stav, délka) → **sdílený mirror** `scb_session_index` (signalem při uložení).
- Reporting základní vrstva běží proti public, detail otevíráš v tenant schema.
- Implementuje se až bude potřeba — zatím připravit hook v signals.

---

## 8. Návazné kroky

Po odsouhlasení otázek:

1. Vytvořit `apps/identity/` — modely Person, Organization, PersonIdentity, PersonOrganizationRole.
2. Migrace konektorů — přidat FK `person_id` / `organization_id` na existující sync tabulky.
3. IdentityResolver service — exact + fuzzy + AI match.
4. Provenance fields na všechny sync tabulky (`source_synced_at`, `source_id`, `raw_payload`).
5. Insight function `client_360(org_id)` jako první cross-system agregace.
6. LangGraph agent "Client 360" + citation rendering.

---

*Připraveno: Claude na základě diskuse s Broňkem | květen 2026 | Scaleupboard / Sentinex*
