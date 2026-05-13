# Google Workspace — API capability sheet

> **Scope:** Scaleupboard Google Workspace domain, employee-facing only.
> **Source of truth for:** team kalendář (1:1 termíny, obchodní schůzky), Drive dokumenty SCB, Gmail (volitelné).
> **Docs:** https://developers.google.com/workspace
> **Související:** `docs/GOOGLE_WORKSPACE_DWD.md` (Domain-Wide Delegation setup).

---

## Autentizace — Service Account + Domain-Wide Delegation (DWD)

Pro SCB use case (server-side ingest dat napříč doménou) **doporučeno service account s DWD**:

1. V Google Cloud Console vytvořit Service Account.
2. Vygenerovat JSON klíč → uložit šifrovaně.
3. Aktivovat Domain-Wide Delegation → získat Client ID.
4. Admin SCB v Google Admin Console → **Security → API Controls → Domain-wide Delegation** → přidat Client ID s scope list.
5. Server pak může impersonovat libovolného uživatele z domény: `credentials.with_subject("user@scaleupboard.com")`.

**Bez DWD:** OAuth flow per uživatel — méně škálovatelné pro automatický ingest.

### Scopes (minimální)

| Scope | Účel |
| --- | --- |
| `https://www.googleapis.com/auth/admin.directory.user.readonly` | Seznam uživatelů v doméně |
| `https://www.googleapis.com/auth/admin.directory.group.readonly` | Skupiny / týmy |
| `https://www.googleapis.com/auth/calendar.readonly` | Kalendář (events) |
| `https://www.googleapis.com/auth/drive.metadata.readonly` | Drive metadata (názvy, vlastníci, sdílení) |
| `https://www.googleapis.com/auth/drive.readonly` | Drive obsah (jen pokud chceme extract textu z docs) |
| `https://www.googleapis.com/auth/gmail.readonly` | Gmail (volitelné, jen pokud chceme analyzovat email komunikaci) |
| `https://www.googleapis.com/auth/contacts.readonly` | Kontakty Google People API |

⚠️ **Gmail je nejcitlivější** — diskuse, jestli zapojovat (privacy, GDPR, vendor lock). Doporučuju neaktivovat pro MVP.

## Rate limits

Google Workspace APIs mají per-user a per-project quoty:
- **Calendar API**: 1M req/day per project, 60 req/min per user.
- **Drive API**: 1B queries/day per project, 1000 req/100s per user.
- **Admin Directory**: 2400 req/min per project.
- **Gmail**: 1.2B quota units/day, kvóty per uživatel.

Exponential backoff na 403/429. Slack-style worker scheduler.

## Klíčové endpointy a co vrací

### Admin Directory API
| Endpoint | Co vrací | Mapping |
| --- | --- | --- |
| `GET /admin/directory/v1/users` | Uživatelé domény: id, primaryEmail, name, orgUnitPath, suspended, lastLoginTime | → `Person(person_type=team)` + `PersonIdentity(email, google_id)` |
| `GET /admin/directory/v1/groups` | Skupiny: id, email, name, members | → `Person`-`Person` mapping (kdo je v jakém týmu) |

### Calendar API
| Endpoint | Co vrací | Mapping |
| --- | --- | --- |
| `GET /calendar/v3/calendars/{calId}/events` | Eventy: id, summary, description, start, end, attendees (s email), organizer, location, hangoutLink, recurringEventId | → `scb_google_event` |
| `GET /calendar/v3/users/me/calendarList` | Kalendáře přístupné uživateli | identifikace primary |

Event je často klíčový datový bod: 1:1 termín, obchodní schůzka, demo. Attendees → resolver na `Person`.

### Drive API
| Endpoint | Co vrací | Mapping |
| --- | --- | --- |
| `GET /drive/v3/files` | Soubory: id, name, mimeType, owners, sharingUser, modifiedTime, parents, shared, webViewLink | → `scb_google_drive_file` (metadata) |
| `GET /drive/v3/files/{id}/export` | Export Google Doc → text/plain pro embedding | obsah pro RAG |
| `GET /drive/v3/changes` | Incremental changes (changeToken) | inkrement sync |

### People API (kontakty)
| Endpoint | Co vrací | Mapping |
| --- | --- | --- |
| `GET /people/v1/people:searchContacts` | Hledání v kontaktech | doplnění Person |
| `GET /people/v1/people/{resourceName}` | Detail kontaktu | metadata |

### Gmail API (volitelné, neprioritizujeme)
| Endpoint | Účel |
| --- | --- |
| `users.messages.list` / `.get` | Emaily, threads |
| `users.history.list` | Inkrement změn |

## Datový model

```
GoogleWorkspaceAccount  (1 per workspace, shared schema)
├─ id, domain (scaleupboard.com)
├─ service_account_json (encrypted)
├─ delegated_admin_email (impersonated)
├─ scopes (array)
└─ installed_at, last_sync_at

GoogleUser  (mirror admin directory, optional — Person má vše)
├─ id, google_id, primary_email, org_unit, suspended, last_login_at
└─ person_id (FK)

scb_google_event
├─ id (UUID)
├─ google_event_id
├─ calendar_id, calendar_owner_person_id
├─ summary, description
├─ start_at, end_at, all_day, timezone
├─ location, hangout_link
├─ organizer_person_id (FK identity.Person)
├─ attendees (JSONB → array of {person_id, email, response_status})
├─ recurring_event_id (parent if recurring)
├─ source_synced_at
├─ source_id = google_event_id
└─ raw_payload

scb_google_drive_file
├─ id, google_file_id
├─ name, mime_type, size
├─ owner_person_id, parents (array)
├─ shared_with_person_ids (array)
├─ web_view_link
├─ modified_at_in_google, source_synced_at
└─ raw_payload

scb_google_drive_content  (extract jen pro vybrané typy)
├─ file_id (FK), extracted_text, extracted_at
└─ extract_method (export | tika | pdf_ocr)
```

## Identity resolution

```
Google user → PersonRecord(
  source_system=google,
  email=user.primaryEmail,
  full_name=user.name.fullName,
  extra_identities={"google_id": user.id},
) → IdentityResolver
```

Calendar event attendee:
```
Attendee email → IdentityResolver (email exact)
```

## Sync strategie

- **Directory users**: 1×/den (málo se mění).
- **Calendar events**: každých 15 min, sync ±90 dní okolo `now` (`timeMin`, `timeMax`).
- **Drive**: incremental přes `changes.list` + changeToken — každou hodinu.
- **Drive content extract** (Docs/Sheets/PDF → text): jen u označených složek/typů, lazy on-demand pro RAG embedding.

## Use cases pro AI

- "Kdy mám další 1:1 s klientem ACME?" → `scb_google_event WHERE attendees contains ACME`.
- "Co se řešilo na schůzce X minulý týden?" → event + odkazovaný Drive zápis + Zoom transcript.
- "Najdi prezentaci o programu Founder" → Drive content embedding.

## Otevřené body

- **Gmail ano/ne pro MVP?** Doporučuju ne (citlivé, vendor lock, jiný workflow). Pokud ano: úzký scope.
- **Které kalendáře sledovat?** Všechny uživatelské, nebo i sdílené (room/resource)?
- **Které Drive složky extract obsahu?** Typicky "Klienti/", "Materiály/", "Sales/" — diskuse s Pavlem.
- **DWD setup** — připravený admin přístup do Google Admin Console (Pavel/Petr).
