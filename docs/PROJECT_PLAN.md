# Sentinex — celkový plán vývoje

> **Verze:** 1.0 — květen 2026
> **Účel:** Souhrnný přehled všeho, co je potřeba postavit napříč celým projektem Sentinex. Slouží jako navigace pro plánování sprintů.
> **Související dokumenty:** `bronislav/ai-bryan-dokument-v11.md`, `bronislav/bryan-plan-vyvoje-v1.md`, `bronislav/sentinex-architektura-a-plan.md`, `docs/ARCHITECTURE.md`, `docs/TODO.md`.

---

## A. Backbone / fundamenty

Bez těchto vrstev nelze stavět nic dalšího.

1. **Identity & Organization layer** — Person, Organization, PersonIdentity, role, merge/audit.
2. **Multi-tenancy** — per-klient schémata, tenant resolution, izolace.
3. **Connector framework** — společný interface, OAuth/API keys (šifrované), sync scheduler, last-sync, retry, error reporting.
4. **Provenance & citation layer** — každý fakt nese zdroj, čas, confidence.
5. **Sentinex ↔ BR API** — service tokens, request/response protokol, agent invocation.
6. **Langfuse jako master prompt registry** — fetcher service, migrace BR `prompts.yaml`.
7. **RBAC / Scope model** — role + per-row scope (kdo vidí co), guardrail pro důvěrná 1:1 data.
8. **Audit log** — kdo/co/kdy/proč, hlavně pro AI rozhodnutí a merge identit.

---

## B. Konektory / data ingest

Pořadí podle priority pro customer journey.

1. **Pipedrive** — sales pipeline, kontakty, dealy, aktivity.
2. **FAPI** — faktury, platby, stav účtu (source of truth pro fakturaci).
3. **Slack** — interní tým (channely), posílání zpráv z BR.
4. **BR** — coaching data, výzvy, SCL/TMF, finanční výkazy (po sjednocení DB).
5. **Zoom** — přepisy schůzek (interní porady, obchodní schůzky, 1:1).
6. **Google Workspace** — kalendář, dokumenty, tabulky.
7. **Merk** — data o potenciálním klientovi před obchodní schůzkou.
8. **Symfio** — finanční reporty, cashflow, manažerské výkazy.
9. **ABRA** — pokud se rozhodne (alternativa FAPI).
10. **MGS** — interní firemní data.
11. **Firemní web s členskou sekcí** — aktivita členů, stažené materiály.

Pro každý konektor: model, sync job, identity mapping, provenance, testy, monitoring, dokumentace.

---

## C. AI / Agent vrstva

1. **Migrace BR superagent → LangGraph** — nahradit IntentClassifier→AgentRouter→ContextAggregator.
2. **10 specializovaných agentů** (z bryan v1.1):
   AI CFO, Strategizer, Team Coach, Customer Expert, BMC Guide, Personal Strategist, A-Player Builder, Job Scorecard Expert, Barrier Coach, Priority Guide.
3. **Orchestrátor** — rozhoduje, kterého specialistu zapojit, jak složit odpověď.
4. **Citation engine** — každé tvrzení agenta má citaci zdroje.
5. **Cost optimization** — routing levný/drahý model, prompt caching, batch zpracování, lokální embeddingy.
6. **Tool use** — agenti volají insight functions místo přímého SQL.
7. **Pre-call & post-call guardrails** — cost budget, scope check, PII masking, output validation.
8. **Feedback loop** — hodnocení odpovědí, učení relevance, prioritizace zdrojů.

---

## D. Memory / znalostní graf

1. **pgvector embeddings** — semantic search nad všemi zdroji.
2. **Hybrid search** — fulltext + vektor + filtry podle času a typu zdroje.
3. **Graphiti + Neo4j** — temporální graf entit a vztahů (klient ↔ deal ↔ schůzka ↔ cíl).
4. **Entity resolution / deduplikace** — automatické rozpoznání stejných entit napříč systémy.
5. **Memory layer pro agenty** — krátkodobá (konverzační) + dlouhodobá (klientský kontext).
6. **Three-layer extraction pipeline** (`docs/TODO.md` #5).

---

## E. Event bus / asynchronní procesy

1. **Kafka topology** — topiky pro každý zdroj (pipedrive.deals, fapi.invoices, slack.messages…).
2. **Consumers** — embedding worker, graph builder, identity matcher, analytics sink.
3. **Celery beat scheduler** — periodické syncy konektorů, weekly briefingy, retention joby.
4. **Real-time hooks** (později) — Slack Events API, Pipedrive webhooks.

---

## F. Analytics & observabilita

1. **ClickHouse** — agentní volání, použití konektorů, response times, token consumption per tenant.
2. **Langfuse** — LLM tracing, evals, prompt experiments.
3. **Sentry** — error tracking (už nasazeno).
4. **Cost monitoring per tenant** — kolik klient stojí na AI, limity, alerty.
5. **Usage tracker** — pro budoucí billing/fakturaci klientům.

---

## G. UI vrstva

Zatím v BR repu, později konsoliduje do Sentinexu.

### G.1 Customer-facing dashboardy
1. **Level 1 dashboard** — sales link bez hesla, salesový screen, L/S/E/C záznam.
2. **Level 2 komunitní dashboard** — widgety dle programů, Academy, akce, novinky.
3. **Komunitní widget + AI matching** — profily členů, 3–5 doporučení, propojení přes Slack.
4. **Slack briefing** — týdenní souhrn (CEO, sales, kouč…).
5. **Onboarding wizard** — 4 kroky (profil, SCL/TMF, finance, termín 1:1).
6. **Chat s AI orchestrátorem + výběr specialisty.**
7. **Widgety programů** — aktivují se po potvrzení programu.

### G.2 Role-based dashboardy
1. Sales
2. Senior kouč
3. Kouč (rozšířený stávající)
4. Vedoucí koučů
5. Community manager
6. Backoffice
7. Admin / SemiAdmin

### G.3 Admin nástroje (Sentinex)
1. Identity merge UI — ruční merge/split entit.
2. Connector management — připojit/odpojit, sync status, error log.
3. Tenant management — vytvořit klienta, schema, RBAC.
4. Prompt management — návaznost na Langfuse.

---

## H. Procesy / business workflow

1. **Sales workflow** — link generation, screen, záznam, odemčení výstupu, předání kouči.
2. **Onboarding workflow** — fee payment, heslo, 4 kroky, upomínky.
3. **Coaching workflow** — 1:1 sezení, výzvy, doporučení programu.
4. **Nabídka programu (Krok 4b)** — blokované rozhodnutí, kdo dotahuje.
5. **Komunitní workflow** — matching, propojení, akce, briefingy.
6. **Fakturační workflow** — FAPI/ABRA, stav plateb, faktury.

---

## I. Deployment & ops

1. **Docker compose** — všechny služby (Postgres, Redis, Kafka, Neo4j, ClickHouse, Langfuse, app, worker, beat).
2. **CI/CD** — GitHub Actions, testy, type check, lint, deploy.
3. **Hetzner production setup** — zero-downtime deploy, Nginx, backups.
4. **Migrace na produkci po BR refaktoru** — sjednocení DB, přechod Supabase → local.
5. **GDPR compliance** — retention, právo na výmaz, audit, šifrování PII.
6. **Security audit** — před ostrým provozem.

---

## J. Testing & quality

1. **Unit testy** insight functions, agents, resolvers.
2. **Integration testy** napříč konektory.
3. **Smoke testy** — health checks (už existují).
4. **AI evals** — Langfuse, dataset golden questions, regression suite.
5. **Tenant isolation testy** — povinné.
6. **Load testy** před produkcí.

---

## K. Dokumentace

Průběžně (per CLAUDE.md):
- `docs/ARCHITECTURE.md`, `AGENTS.md`, `DATA_ACCESS.md`, `CONNECTORS.md`, `SECURITY.md`, `DEPLOYMENT.md`
- Per-connector docs (např. `docs/GOOGLE_WORKSPACE_DWD.md`).
- Onboarding pro vývojáře.
- Návody pro každou roli (Sales, Kouč, Community manager…).

---

## Časová orientace (z bryan plánu vývoje)

**Květen–září 2026, 5 měsíců, 700–800 hodin, 385 000 Kč.**

Hrubě mapováno na bloky:

| Měsíc | Milník | Bloky |
| --- | --- | --- |
| Květen | M0 — Základ + BR modernizace | A.1–A.6, část I.1 |
| Červen | M1 — Centrální DB + nový obchodní model | B.1–B.4 (Pipedrive, FAPI, BR, Slack), C.1 (LangGraph migrace), G.1.1+G.1.5 v BR |
| Červenec | 🎯 M2 — AI s citacemi + první testovatelná verze | C.2–C.4 (specialisté, citation), G.1.6 (chat), web s členskou sekcí |
| Srpen | M3 — Orchestrace + graf + UI | C.3 (orchestrátor), D.3 (Graphiti graf), G.1.4 (briefing), G.2 (role dashboardy) |
| Září | 🚀 M4 — Ladění a ostrý provoz | J (testing, evals), I.3+I.5 (deploy, GDPR), ladění, dokumentace |

---

## Otevřené body k rozhodnutí

| # | Téma | Kdo | Stav |
| --- | --- | --- | --- |
| 1 | Person scope (jen klienti vs. všichni) | Broněk | otevřeno |
| 2 | Organization model + PersonOrganizationRole | Broněk | otevřeno |
| 3 | Merge UI: Sentinex admin vs. BR | Broněk | otevřeno |
| 4 | Který konektor jako první (Pipedrive vs. FAPI) | Broněk | doporučeno Pipedrive |
| 5 | Per-tenant schémata teď, nebo po BR refaktoru | Broněk | doporučeno teď (placeholder) |
| 6 | Odhad termínu BR refaktoru | Broněk | otevřeno |
| 7 | Krok 4b — kdo dotahuje nabídku programu | Pavel + Petr | blokuje M9 |
| 8 | FAPI vs. ABRA vs. Symfio — sjednotit | Broněk + Pavel | otevřeno |

---

*Připraveno: Claude na základě diskuse s Broňkem | květen 2026 | Scaleupboard / Sentinex*
