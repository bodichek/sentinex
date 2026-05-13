# Sentinex — role, práva a klasifikace dat

> **Verze:** 1.0 — květen 2026
> **Status:** návrh k odsouhlasení (před implementací).
> **Účel:** Nastavit RBAC + data classification ještě před připojením konektorů, aby každý embedding a každá retrieval query od dne 1 respektovala scope. Retrofitting access control do vector store je drahý.

---

## 1. Šest vrstev access controlu

### Vrstva 1: Role & permissions

```
Role
  - code: sales | senior_coach | coach | coach_lead |
          community_manager | backoffice | admin |
          client | client_team
  - name, description

Permission
  - code: view_1on1_content, view_1on1_metadata, view_finance,
          view_sales_pipeline, view_community, view_billing,
          edit_coaching, cross_tenant_query, merge_identities,
          manage_connectors, …

RolePermission                  ← Role × Permission (M2M)

RoleAssignment
  - user (FK)
  - role (FK)
  - organization (FK, nullable)  ← "kouč kouchuje konkrétní firmy"
  - granted_by, granted_at, expires_at
```

### Vrstva 2: Data classification

Každý záznam i embedding nese klasifikaci:

```
DataClass (enum)
  - one_on_one_content        ← důvěrné — jen kouč + senior + klient
  - one_on_one_metadata       ← datum, kouč, stav — pro reporting
  - finance                   ← finanční výkazy klienta
  - sales_pipeline            ← Pipedrive, jen sales + SCB team
  - billing                   ← FAPI, jen backoffice
  - community                 ← komunitní profily, akce, novinky
  - knowledge_internal        ← interní SCB knowledge base
  - knowledge_client_facing   ← veřejné materiály
  - public                    ← bez omezení

VisibilityScope (každý záznam má)
  - organization_id           ← KOHO se týká
  - person_id                 ← volitelné, vázané na konkrétní 1:1
  - data_class
  - extra_role_codes (array)  ← override "vidí navíc tyto role"
```

### Vrstva 3: Scope evaluator

Centrální service spočte, co uživatel může:

```python
class AccessScope:
    user_id: UUID
    role_codes: set[str]
    permissions: set[str]                   # spočtené z rolí
    accessible_org_ids: set[UUID] | "ALL"   # podle RoleAssignment
    accessible_data_classes: set[str]       # spočtené z permissions

def build_access_scope(user) -> AccessScope: ...
```

### Vrstva 4: Vector store integrace (klíčové)

`MemoryEmbedding` dostane fields:

```
- data_class
- organization_id
- person_id (nullable)
- visibility_scope (rychlé filtrační pole)
```

Retrieval projde **pre-filterem** před similarity search:

```python
def retrieve(query, viewer: AccessScope, k=10):
    qs = MemoryEmbedding.objects.filter(
        data_class__in=viewer.accessible_data_classes,
        organization_id__in=viewer.accessible_org_ids,
    )
    return qs.order_by(L2Distance("embedding", query_vec))[:k]
```

Pre-filter > post-filter — bezpečnější + rychlejší (pgvector pracuje s menším setem).

### Vrstva 5: LangGraph agent context

Každý agent dostane `viewer: AccessScope` ve stavu grafu. Tooly a insight functions dostávají viewer jako první parametr a respektují ho. Guardrail to vynutí — nelze obejít.

### Vrstva 6: Audit log

Každý retrieval, každý agent run loguje:
- viewer (user, role)
- accessed_data_classes
- accessed_org_ids
- query / function called
- timestamp

Audit log vidí Senior kouč nebo Admin.

---

## 2. Default role matrix (návrh)

| Role | 1:1 content | 1:1 meta | Finance | Sales | Billing | Community | Cross-tenant |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Admin | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Senior coach | ✓ scoped | ✓ | ✓ | ✓ | – | ✓ | ✓ scoped |
| Coach | ✓ vlastní klienti | ✓ scoped | ✓ scoped | – | – | ✓ | – |
| Coach lead | metadata | ✓ | ✓ scoped | – | – | ✓ | reporting only |
| Sales | – | – | – | ✓ | – | – | – |
| Backoffice | – | – | – | – | ✓ | – | reporting only |
| Community manager | – | – | – | – | – | ✓ | reporting only |
| Client | vlastní | vlastní | vlastní | – | vlastní faktury | ✓ | – |
| Client team | scoped | scoped | scoped | – | – | – | – |

"Scoped" = jen u Organization, kam je uživatel přiřazen přes `RoleAssignment`.

---

## 3. Plán implementace

1. `apps/access/` (nebo součást `apps/core/`) — modely Role, Permission, RolePermission, RoleAssignment + data migrace s default rolí a permissions.
2. `AccessScope` builder service.
3. DataClassification fields na `MemoryEmbedding` (migrace `apps/agents`).
4. Retrieval helper s pre-filtrem (`apps/memory` / `apps/agents`).
5. Hook do `apps/agents/` — viewer ve stavu LangGraph, guardrail kontroluje.
6. Decorator `@requires_permission("view_1on1_content")` pro views.
7. Audit log model + middleware.
8. Testy: izolace rolí, kouč nevidí cizí 1:1, klient nevidí cross-client, vector retrieval respektuje scope.

---

## 4. Otevřené otázky k rozhodnutí

| # | Otázka | Návrh |
| --- | --- | --- |
| 1 | Souhlasí default matrix? | – |
| 2 | Vidí Sales finance klienta? | Spíš ne (předává koučovi). Potvrdit. |
| 3 | Vidí klient svoje 1:1 přepisy? | Dokument říká ano; plný transcript možná ne. |
| 4 | Vidí Senior kouč klienty jiného Senior kouče? | Cross-tenant ano, ale možná jen metadata, ne 1:1 content. |
| 5 | Bude existovat role „observer" (read-only audit)? | Pro GDPR / compliance pravděpodobně ano. |
| 6 | Mezityhle role nebo permission overlays (např. „auditor" jako dočasná role na X dnů)? | Implementovat přes `expires_at` na RoleAssignment. |

---

## 5. Proč to dělat před připojením konektorů

- **Vector store classification je load-bearing.** Když uložíme miliony embeddingů bez `data_class`, retrofit znamená re-embedding všeho — drahé časově i tokeny.
- **Provenance ↔ visibility.** Konektor musí při zápisu vědět, do jaké classification dat patří (FAPI faktura → `billing`, Pipedrive deal → `sales_pipeline`, BR coaching session → `one_on_one_content`).
- **Bez RBAC se nedá uvést první test s reálnými klienty.** Klient by viděl všechno.
- **Audit log od dne 1** = GDPR-ready.

---

*Připraveno: Claude na základě diskuse s Broňkem | květen 2026 | Scaleupboard / Sentinex*
