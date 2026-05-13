# Broněk — osobní TODO

> Soubor, který používá Claude jako tvůj osobní task list. Cokoliv tady je
> **na tobě**, ne na Claudovi. Claude do něj zapisuje nové otevřené body,
> ty je odbavuješ. Po vyřešení označ `[x]` a/nebo přesuň do "✅ Hotovo".

---

## 🔴 Blokující rozhodnutí (čekají na tebe)

- [ ] **RBAC + data classification** — schválit návrh v `bronislav/sentinex-role-a-prava.md`
  - Default role matrix (sekce 2) — souhlas / úpravy?
  - Otázky 1–6 v sekci 4 (Sales vidí finance? Klient vidí 1:1 transcript? Cross-tenant Senior kouč? Observer role? Time-bound role assignments?)
  - **Bez schválení nemůžeme stavět** vector store data classification → každý další embedding bude třeba později re-tagovat (drahé).

- [ ] **Krok 4b — kdo dotahuje nabídku programu** (z bryan v1.1 doc)
  - Pavel + Petr
  - Blokuje milník M9 a definici Senior kouč dashboardu.

- [ ] **FAPI vs ABRA vs Symfio** — sjednotit source of truth pro fakturaci
  - Bryan plán zmiňuje FAPI + Symfio, AI Bryan doc FAPI/ABRA
  - Rozhodnout: jeden master pro vystavené faktury, ostatní jen pro reporty?

---

## 🟡 Inputs / přístupy / API klíče

- [ ] **FAPI API přístup**
  - Login do FAPI účtu SCB → `Nastavení → API přístupy` → vygenerovat klíč
  - Sdílet API dokumentaci (PDF/screenshot/odkaz) — pro doplnění `docs/connectors/fapi.md` (⚠ ověř sekce: base URL, exact endpoints, rate limity, sandbox)
  - Které custom fields FAPI SCB používá (typ klienta, atribuce, segment) — workshop s backofficem
  - Webhook signature secret (HMAC) pokud zapojíme webhooks

- [ ] **Merk.cz API klíč**
  - Z účtu Merk SCB (nebo přes informace@imper.cz)
  - Limit batch volání / měsíc na plánu SCB
  - Dokumentace `api.merk.cz/docs/` (nebo PDF) — pro doplnění přesných URL endpointů
  - Které extra fieldy (>100) chceme strukturované vs. v `raw_payload`

- [ ] **Pipedrive custom fields mapping** (workshop s Petrem)
  - Které custom fields na Organization / Person / Deal SCB používá
  - Mapping stage → fáze customer journey (sales → onboarding → coaching)
  - **Které Pipedrive custom fields plnit enrichmentem** (návrh: 10 polí — IČO, DIČ, obrat range, employees range, Merk rating, NACE, web, segment, recommended program, Sentinex profile URL)

- [ ] **Slack workspace setup**
  - Vytvořit Slack App v `api.slack.com/apps` pro SCB workspace (jen pokud ještě není)
  - Nastavit scopes (viz `docs/connectors/slack.md` sekce Autentizace)
  - Pozvat bota do channelů, které chceme tracket
  - **Které channely sledovat od dne 1?** (návrh: `#sales`, `#coaching`, `#ops`, `#dev`)
  - Kam má bot posílat briefingy: DM koučovi? Channel `#briefings`? Oba?
  - Bot identity: psát jménem konkrétního kouče, nebo univerzálně "Bryan"?

- [ ] **Google Workspace** (až bude na řadě)
  - Service Account v Google Cloud Console
  - Domain-Wide Delegation v Admin Console (viz `docs/GOOGLE_WORKSPACE_DWD.md`)
  - **Gmail zapojit ano/ne?** (doporučení Claude: ne pro MVP)
  - Které Drive složky extract obsahu (Klienti/, Materiály/, Sales/?)

- [ ] **Supabase access token** — pro Claude MCP integraci (deferred, asi až bude reálná potřeba dotazovat externí DB)

- [ ] **GitHub MCP** — interaktivně přes `/mcp` v Claude Code (jednorázový OAuth)

- [ ] **Google Drive auth** — interaktivně přes `/mcp` v Claude Code (jednorázový OAuth)

---

## 🟢 Procesní rozhodnutí (delegovatelné na tým)

- [ ] **Workshop se salesem** (Pavel + Petr) — `bronislav/ai-bryan-dokument-v11 (1).md` sekce 8.1 P1
  - Obsah salesového screenu (co obchodník zaznamenává, co a kdy vidí klient)
  - Logika odemčení výstupu po schůzce
  - Pipedrive napojení strategy

- [ ] **Workshop s Helenou** — sekce 8.1 P2
  - Rozhodovací kritéria pro doporučení programu
  - Role kouče vs. senior kouče
  - Zpětná vazba klientů (mechanismus)
  - Obsah dashboardů (kouč, vedoucí koučů)

- [ ] **Trello → BR migrace** (Pavel + Martina)
  - Co z Trella přechází do BR community manager
  - Co zůstane mimo systém

- [ ] **Přehled akcí a novinek** (Pavel + Martina)
  - Pouze marketing ruční / pouze AI / kombinace?

- [ ] **Nabídka programu v BR** (Pavel + Helena + David)
  - Pouze informace / cena + potvrzení / plný checkout?

---

## 🔵 Tech rozhodnutí (delegovatelné na Claude, ale potřebuji tvůj signál)

- [ ] **Pipedrive enrichment write-back trigger** — kdy psát do custom fields?
  - Doporučení Claude: **hned** pro confidence > 0.9, **human confirm** pro 0.7–0.9, **nic** pod 0.7
  - Tvoje volba?

- [ ] **Slack ingest frekvence** — batch sync 15 min stačí, nebo near-real-time Events API od dne 1?
  - Doporučení Claude: 15 min stačí, real-time později

- [ ] **Per-tenant schema lifecycle** — kdy schema vytvořit?
  - Hned při označení Organization jako "client", nebo až po platbě FAPI?
  - Doporučení Claude: až po `BrRegistrationSignal` přejde do `confirmed`

- [ ] **Retention policy raw_payload** — 90 dní (default) OK, nebo jiná hodnota?

- [ ] **Pipedrive webhook ano/ne pro real-time enrichment**
  - Bez webhooks: 15min latence mezi novým kontaktem a enrichmentem
  - S webhooks: ~5 sec, ale složitější setup (veřejný URL, HMAC validation)

---

## 📝 Otevřené body pro budoucí review

- [ ] **BR refaktor timeline** — kdy bude BR vmergovatelný do Sentinexu?
- [ ] **Mobilní aplikace** — kdy začít? (bryan plán: navazující rozvoj, mimo MVP)
- [ ] **Cost monitoring per tenant** — kdy nastavit alerts? (po prvních 5 klientech?)
- [ ] **Security audit** — před ostrým provozem (září 2026)
- [ ] **GDPR retention review** — kdo je data controller (SCB) vs. processor (Sentinex)?
- [ ] **CI cleanup** — pre-existing baseline ~70 ruff errors + ~380 mypy errors v `apps/agents`, `apps/analytics`, `apps/observability`, `apps/chat`, `apps/data_access`, `apps/connectors/{fapi/sync.py,pipedrive/client.py}`. Tyto chyby předcházejí ingest framework práci. Potřeba samostatný cleanup PR — odhad 2–3 h ručně, nebo `ruff --fix --unsafe-fixes` + manual type annotation pass.

---

## ✅ Hotovo

- [x] Sentinex architektura + DB struktura — návrh schválený (Sentinex DB master, per-tenant schémata, FAPI/Pipedrive source of truth)
- [x] Identity & Organization layer (`apps/identity/`) postavené + testy
- [x] Connector framework (`apps/connectors/_framework/`) postavený + testy
- [x] Pipedrive ingest (organizations, persons, deals, activities)
- [x] FAPI ingest (customers, invoices)
- [x] Slack ingest (workspace, users, channels, messages)
- [x] Merk konektor (scaffold + client + on-demand enrich)
- [x] Capability sheets pro 5 priority-1 konektorů (`docs/connectors/`)
- [x] Core docs sync (ARCHITECTURE, CONNECTORS, DATA_ACCESS, SECURITY)
- [x] Claude Code setup (pluginy, MCP, dokumentace)

---

*Poslední aktualizace: 2026-05-13*
