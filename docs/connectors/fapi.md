# FAPI — API capability sheet

> **Scope:** Scaleupboard own FAPI account, employee-facing only.
> **Source of truth for:** fakturace klientům, stav plateb, odběry.
> **Docs:** veřejná dokumentace v help.fapi.cz / API sekce v aplikaci po přihlášení.
> **Status:** některé detaily vyžadují potvrzení podle reálného FAPI plánu SCB — označeno **⚠️ ověř**.

---

## Autentizace

- **API klíč + username (Basic Auth)** — standardní FAPI API model.
- Header: `Authorization: Basic base64(username:api_key)`.
- API klíč najdeš v FAPI: **Nastavení → API přístupy**.
- Klíč uložit šifrovaně přes `django-cryptography`.

⚠️ ověř: některé plány FAPI mají API jen v Business / Premium tieru.

## Rate limits

- ⚠️ ověř — FAPI veřejně neuvádí přesné limity. V praxi se setkáváme s ~60 req/min. Implementovat retry s exponential backoff a respektovat `Retry-After` hlavičku.

## Klíčové endpointy a co vrací

(Pojmenování odpovídá FAPI v1 API, kdy resources mají český kontext.)

| Endpoint | Co vrací | Mapping do Sentinex |
| --- | --- | --- |
| `GET /invoices` | Faktury: id, number, customer, amount, vat, currency, issued_at, due_at, paid_at, status, items | → `scb_fapi_invoice` |
| `GET /invoices/{id}/pdf` | PDF faktury — neukládáme, jen reference URL | – |
| `GET /customers` | Odběratelé: id, name, ICO, DIC, email, phone, address, billing_email | → `Organization` + `OrganizationIdentity(fapi_customer_id, ICO, DIC)` |
| `GET /payments` | Platby: id, invoice_id, amount, paid_at, method (card/bank/cash) | → `scb_fapi_payment` |
| `GET /subscriptions` | Předplatné: id, customer, plan, start, end, next_invoice_at, status | → `scb_fapi_subscription` |
| `GET /products` (vouchers) | Produkty / programy (Founder, Scale, Excel…) | → `scb_fapi_product` |
| `GET /vouchers` | Slevové kódy / dárkové kupony | → referenční |
| `GET /forms` | Online objednávkové formuláře | → `scb_fapi_form` |
| `POST /webhooks` | Registrace webhooks | viz níže |

⚠️ ověř přesný tvar endpointů a parametrů z FAPI dokumentace na účtu SCB.

## Webhooks

FAPI nabízí webhooks pro klíčové eventy:
- `invoice.created`, `invoice.paid`, `invoice.overdue`
- `payment.received`
- `subscription.renewed`, `subscription.cancelled`
- `form.submitted` (nový lead z webu)

Doporučeno: **webhooks pro real-time** + batch reconcile každou hodinu.

## Datový model v Sentinexu

```
scb_fapi_invoice
├─ id (UUID)
├─ fapi_id (str, unique)
├─ number (str, např. "2026/0042")
├─ organization_id  → identity.Organization (resolved přes ICO nebo customer email)
├─ fapi_customer_id (raw)
├─ amount, vat_amount, currency
├─ status: draft | sent | partial | paid | overdue | cancelled
├─ issued_at, due_at, paid_at
├─ days_overdue (computed)
├─ items (JSONB, položky faktury)
├─ source_synced_at
├─ source_id = fapi_id
└─ raw_payload (JSONB, 90d retention)

scb_fapi_payment
├─ id, fapi_id, invoice_id (FK), organization_id
├─ amount, currency, method, paid_at
├─ source_synced_at, raw_payload

scb_fapi_customer
├─ id, fapi_id, organization_id (resolved)
├─ name, ico, dic, billing_email, phone, address (JSONB)
├─ raw_payload
(pomocná tabulka — Organization je master)

scb_fapi_subscription
├─ id, fapi_id, organization_id, product_id
├─ plan, status (active/cancelled/expired)
├─ start_date, end_date, next_invoice_at
├─ raw_payload

scb_fapi_product (číselník)
├─ fapi_id, name, type (one_time | recurring), price, currency
```

## Identity resolution flow

```
FAPI customer → OrganizationRecord(
  source_system=fapi,
  name=customer.name,
  ico=customer.ico,        ← klíčové pro match na český registr
  dic=customer.dic,
  id_in_source=fapi_customer_id,
) → IdentityResolver
```

FAPI billing_email → PersonRecord(person_type=contact, role=billing_contact).

ICO je nejtvrdší identifikátor pro českou firmu. Identity resolver má prioritně matchovat na ICO před fuzzy name match.

## Sync strategie

- **Init**: full backfill (customers, invoices za posledních 24 měsíců, subscriptions, products).
- **Periodic**: každou hodinu inkrement `?updated_since=<last_sync>`.
- **Webhooks**: real-time pro paid/overdue (klíčové pro briefing).
- **Reconcile**: 1×/den full diff (zachytit smazané faktury).

## Co se s daty dělá dál

- **`overdue` faktura > 14 dní** → trigger pro briefing kouči ("klient X má X dní po splatnosti").
- **`subscription.cancelled`** → flag pro Senior kouče ("klient odchází").
- **Embedding položek faktury** — položky popisují, co klient od SCB nakupuje (Founder kurz, mentoring…) → kontext pro AI.

## Otevřené body k ověření

⚠️ Bude potřeba dotáhnout z FAPI účtu SCB / dokumentace:

1. Přesný formát base URL (typicky `https://api.fapi.cz/v1` nebo `https://faktury.fapi.cz/api/v1`).
2. Skutečná rate limit politika.
3. Které custom fields FAPI má SCB nastavené (typ klienta, segment, atribuce na sales…).
4. Jak FAPI rozlišuje opakované subscription invoices vs. jednorázové.
5. Webhook signature validation (security — HMAC).
6. Existuje sandbox / test prostředí?

**Akce:** dej mi přístup do FAPI dokumentace v účtu SCB nebo screenshot API sekce — doplním přesnosti.
