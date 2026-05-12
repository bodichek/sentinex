# Sentinex — architektonická rozhodnutí a plán

> **Verze:** 1.0 — květen 2026
> **Účel:** Zaznamenat klíčová rozhodnutí z diskuse o vztahu Sentinex ↔ BR, identity resolution, Slack ingest a sprintu 0.
> **Status:** živý dokument, aktualizuje se s každým rozhodnutím.

---

## 1. Vztah Sentinex ↔ Business Review (BR)

**Pojmenování:** Sentinex = Bryan = AI Bryan. Různé dokumenty používají různá jména pro stejný projekt.

**Aktuální stav:**
- BR (Scaleupboard, review.scaleupboard.com) je existující Django aplikace, právě se refaktoruje.
- Sentinex je samostatný repozitář — AI/orchestrační backbone (LangGraph, Graphiti+Neo4j, Langfuse, Kafka, ClickHouse, pgvector).
- UI nových funkcí jde zatím **do BR** (HTMX + SCB komponenty), aby nepřibývaly nové frontendy.
- Backend agentů, paměti, eventů a analytiky běží v Sentinexu.

**Cílový stav (po refaktoru BR):**
- BR se vmerguje do Sentinexu.
- Sentinex bude jediná kódová báze.
- UI bude konsolidované v Sentinexu.

**DB strategie:**
- **Sentinex local Postgres (pgvector) = master.** Supabase končí.
- Per-tenant schémata: každý klient (firma) má vlastní schema v Sentinex DB.
- Finální schema layout se doladí po BR refaktoru.

**Source of truth podle domény:**
| Doména | Master systém |
| --- | --- |
| Fakturace, platby | **FAPI** |
| Sales pipeline | **Pipedrive** (dokud nepřevezme kouč) |
| Coaching state | BR (později Sentinex po merge) |
| Cross-system 360° pohled | **Sentinex** (aggregator) |

**Orchestrace:**
- **Varianta A:** Sentinex LangGraph nahrazuje BR `superagent` a `rag` apps.
- Důvod: klasický RAG je pro consulting příliš statický; LangGraph + Graphiti dávají bohatší reasoning.
- Migrace postupná, ale cílový stav = jeden orchestrátor v Sentinexu.

**Prompty:**
- **Langfuse = master.** Všechny prompty žijí v Langfuse.
- BR `prompts/prompts.yaml` + `prompt_manager` se postupně migruje na fetch z Langfuse.
- Žádné nové prompty přímo do `prompts.yaml`.

**Role-based přístup:**
- Každá role (Sales, Senior kouč, Kouč, Vedoucí koučů, Community manager, Backoffice) používá svoji primární aplikaci.
- Sentinex je aggregator napříč těmito aplikacemi — dává každé roli sjednocený pohled.
- Weekly briefingy (CEO Weekly Brief, Sales weekly atd.) jsou typický scénář — bude jich víc.
- 1:1 obsah je důvěrný — tvrdý guardrail na úrovni role.

---

## 2. Identity Resolution

**Problém:** Klient má jiný email ve FAPI (fakturační), jiný v Pipedrive (firemní), jiný v BR (přihlašovací) + Slack ID. Bez sjednocení agent odpoví špatně ("klient nemá faktury" → ve skutečnosti má, ale pod jiným emailem).

### 2.1 Datový model

```
Person (master)
  - id (UUID)
  - display_name
  - primary_email (pro UI)
  - person_type: client | team | contact | vendor
  - confidence_score
  - created_at / merged_into

PersonIdentity (1:N na Person)
  - person_id (FK)
  - identity_type: email | slack_id | slack_handle | pipedrive_id |
                   fapi_id | br_user_id | zoom_email | google_id |
                   phone | linkedin
  - identity_value: string
  - source_system: pipedrive | fapi | br | slack | zoom | google | manual | ai_match
  - verified: bool
  - confidence: float (0.0–1.0)
  - first_seen / last_seen
  UNIQUE(identity_type, identity_value)

Organization (firma)
  - id, name, ico, dic, primary_email_domain, …

PersonOrganizationRole
  - person_id, organization_id
  - role: ceo | coo | cfo | contact | …
  - valid_from / valid_to

PersonMergeLog (audit)
  - person_a, person_b, merged_into
  - matched_by: email_exact | name_company_fuzzy | manual | ai_match | slack_lookup
  - matched_at / matched_by_user
  - undo_token
```

**Pravidla:**
- Person je master, identifikátory jsou hrany (PersonIdentity).
- `UNIQUE(identity_type, identity_value)` — jeden email/slack_id patří právě jedné Person.
- Konektory **nikdy** nepíšou přímo do Person — vždy přes `IdentityResolver`.

### 2.2 Resolver workflow

```
Konektor přinese: {email, name, company, source_system}
  ↓
1. Exact match na PersonIdentity(email)         → high confidence, hotovo
2. Fuzzy match: jméno + doména emailu + firma  → medium confidence
3. AI match: LLM dostane kandidáty + nový       → low/medium confidence
   záznam, vrátí match/no-match/uncertain
4. Uncertain → nová Person + flag pro ruční review
  ↓
Audit log každého rozhodnutí
```

### 2.3 Slack ID auto-detection

- `users.lookupByEmail` přes Slack API → z emailu vrátí Slack `user_id`.
- Při init syncu Slack workspace: `users.list` → pro každého najdi Person přes email (resolver) → vytvoř `PersonIdentity(slack_id)`.
- Fallback: ruční mapping v admin UI.

### 2.4 Implementační pořadí

1. Datový model + migrace (`apps/identity/`).
2. `IdentityResolver` s exact-match + fuzzy (Levenshtein na jméno + email doména).
3. AI matcher (LLM se strukturovaným výstupem).
4. Slack `users.lookupByEmail` job.
5. Admin UI pro ruční merge/split.
6. **Až poté** konektory FAPI/Pipedrive/BR — všechny volají Resolver.

### 2.5 Otevřené otázky

1. Person scope — jen klienti, nebo všichni lidé (interní tým, kontakty, dodavatelé)?
2. Klient = firma + osoba? Tj. `Organization` + `PersonOrganizationRole`?
3. Merge UI — Sentinex admin nebo BR?

---

## 3. Slack ingest

**Priorita pro MVP:** sledovat **interní tým** (komunikace v sales/coaching/dev channelech), ne klienty. Druhý use case: posílání zpráv z BR do Slack.

### 3.1 Datový model

```
SlackWorkspace (1 per tenant)
  - tenant_id, team_id, access_token (encrypted)

SlackChannel
  - workspace_id, channel_id, name, purpose
  - is_tracked: bool (opt-in)
  - sync_from_ts

SlackMessage
  - channel, ts (Slack timestamp = ID), thread_ts
  - slack_user_id, person_id (FK, nullable)
  - text, raw_payload (JSONB)
  - mentioned_person_ids (parsed <@U123>)
  - reactions, file_refs
  - synced_at
  UNIQUE(channel_id, ts)

SlackSyncState
  - channel_id, last_ts, last_synced_at
```

### 3.2 Ingest pipeline

**One-time init:**
1. `users.list` → stáhne tým s emaily.
2. Pro každého `slack_user_id` najdi Person přes email (resolver) → `PersonIdentity(slack_id)`.
3. `conversations.list` → seznam channelů; vyber opt-in (sledované).

**Periodicky (Celery Beat, každých 15–30 min):**
1. Pro každý opt-in channel: `conversations.history` od `last_ts`.
2. Uloží zprávy, doplní `thread_ts` reply (`conversations.replies` pokud thread roste).
3. Aktualizuje `SlackSyncState`.

**Identity v reálném čase:**
- Nový Slack user → `users.info` → resolver → buď Person nalezena, nebo nová + review flag.
- Zpráva od neznámého user_id neblokuje ingest — `person_id=null`, doplní se backfill jobem.

**Embedding & graph (asynchronně, později):**
- Po uložení zprávy → Celery task → embedding do pgvector + node do Graphiti.
- Filtr: krátké zprávy, emoji-only, bot zprávy → přeskočit.
- Pro interní tým není nutné od začátku — strukturovaná data + fulltext stačí.

### 3.3 Posílání z BR

Sentinex vystavuje interní API:

```
POST /api/slack/send
  {
    person_id | channel | slack_user_id,
    text,
    blocks?
  }
```

- Volá `chat.postMessage` přes Slack API.
- BR posílá přes service token.
- Rozšiřitelné o threadování, mentions, buttons.

### 3.4 Co odpadá pro MVP

- DM ingest (ani 1:1, ani group DM).
- Klientské channely (později).
- Real-time Events API přes webhook (později, batch stačí).
- Graphiti node-per-message (později).

### 3.5 Privacy & rate limits

- Žádné DM bez explicitního souhlasu.
- Jen public + private channely, do kterých je Sentinex bot pozván.
- Per-tenant izolace: Slack workspace patří k jednomu tenantu.
- Retention nastavitelná (default 12 měsíců), mazací joby.
- Slack rate limits (Tier 3 = ~50 req/min) — init sync jako resumable job s checkpointy.

### 3.6 Implementační pořadí

1. Modely `SlackWorkspace`, `SlackChannel`, `SlackMessage`, `SlackSyncState`.
2. `SlackClient` service — wrapper nad `slack_sdk`, token z `SlackWorkspace`.
3. Init job: `users.list` + opt-in channely.
4. Celery beat job: `sync_slack_channels`.
5. Endpoint `POST /api/slack/send` pro BR.

**Odhad:** 1–3 dny vývoje + testy.

---

## 4. Sprint 0 — Sentinex backend fundamenty

Pořadí prací **před** prvním konektorem a před milníkem M1 z bryan plánu:

1. **Identity Resolution layer** (`apps/identity/`) — bez tohohle nemá smysl natahávat data odkudkoli. **Priorita #1.**
2. **Per-tenant schema model** — django-tenants už v `pyproject.toml`. Dotáhnout middleware, migrace, šablonu pro vytvoření per-klient schématu.
3. **Connector framework** — společný interface pro Pipedrive/FAPI/Slack/Zoom/Google/Merk/Symfio. OAuth/API key storage (django-cryptography), sync scheduler, error handling, last-sync timestamp.
4. **Provenance/citation layer** — každý záznam z konektoru, embedding, agent odpověď nese `source`, `source_id`, `synced_at`, `confidence`.
5. **Langfuse prompt fetcher service** — rozšířit `apps/observability/prompt_manager.py` o veřejné API pro BR.
6. **Sentinex ↔ BR shared API** — protokol: (a) BR posílá agent request → Sentinex orchestruje → vrací s citacemi, (b) Sentinex čte data BR. Auth přes service tokens.
7. **Slack ingest (interní tým)** — viz sekce 3.

**Doporučené pořadí v rámci sprintu 0:**
1 → 2 → 3 → 6 → 4 → 5 → 7 (Slack jako finální dílek)

---

## 5. Sprint 1 — první cross-system scénář

Cíl: něco funkčního ukázat.

- Konektor **Pipedrive** + **FAPI** běží, synchronizují klienty/dealy/faktury do Sentinex DB (přes resolver).
- LangGraph agent **"Client 360"** — na dotaz "co víme o klientovi X" vrátí strukturovanou odpověď napříč Pipedrive + FAPI + BR, s citacemi.
- Endpoint pro BR, aby BR uměl tuto odpověď zobrazit ve svém UI.

---

## 6. Otevřené body k rozhodnutí

| # | Téma | Kdo rozhoduje | Stav |
| --- | --- | --- | --- |
| 1 | Person scope (jen klienti vs. všichni) | Broněk | otevřeno |
| 2 | Organization model + PersonOrganizationRole | Broněk | otevřeno |
| 3 | Merge UI: Sentinex admin vs. BR | Broněk | otevřeno |
| 4 | Který konektor jako první (Pipedrive vs. FAPI) | Broněk | doporučeno Pipedrive |
| 5 | Per-tenant schémata teď, nebo po BR refaktoru | Broněk | doporučeno teď (placeholder) |
| 6 | Odhad termínu BR refaktoru | Broněk | otevřeno |
| 7 | Krok 4b — kdo dotahuje nabídku programu (z bryan dokumentu) | Pavel + Petr | blokuje M9 |
| 8 | FAPI vs. ABRA vs. Symfio — sjednotit | Broněk + Pavel | otevřeno |

---

*Připraveno: Claude na základě diskuse s Broňkem | květen 2026 | Scaleupboard / Sentinex*
