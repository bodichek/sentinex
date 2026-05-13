# Slack — API capability sheet

> **Scope:** Scaleupboard own Slack workspace, employee-facing only.
> **Source of truth for:** interní team komunikace, posílání zpráv z BR/Sentinexu klientům + týmu.
> **Docs:** https://api.slack.com/

---

## Autentizace

- **Slack app + Bot token** (`xoxb-...`).
- Vytvořit Slack App v `api.slack.com/apps` pro workspace SCB.
- Scope:
  - **Bot scopes:** `channels:history`, `channels:read`, `groups:history`, `groups:read`, `users:read`, `users:read.email`, `chat:write`, `chat:write.public`, `im:write`, `team:read`, `reactions:read`, `files:read`.
  - **User scope** (volitelné): `search:read` pro fulltext.
- Install workspace → získáš `SLACK_BOT_TOKEN`.
- Pro odesílání jménem uživatele: **User OAuth token** (`xoxp-...`) — jen pokud potřebujeme.
- Bot musí být **pozván do každého channelu**, který chceme číst.

Token uložit šifrovaně, scope per workspace.

## Rate limits

Tier-based:
- **Tier 1**: ~1 req/min (rare endpoints jako team.info)
- **Tier 2**: ~20 req/min (conversations.list)
- **Tier 3**: ~50 req/min (conversations.history, messages) ← typický pro nás
- **Tier 4**: ~100 req/min (posting)

Header `Retry-After` při 429. Implementovat globální rate limiter v Celery workeru.

## Klíčové endpointy

| Endpoint | Co vrací | Mapping |
| --- | --- | --- |
| `users.list` | Seznam workspace uživatelů: id, name, real_name, email (s `users:read.email`), tz, deleted | → `Person` + `PersonIdentity(slack_id)` |
| `users.lookupByEmail` | Z emailu vrátí Slack user (klíč k auto-detekci slack_id z FAPI/Pipedrive) | → linker pro existing Person |
| `users.info` | Detail uživatele (single) | doplnění chybějících fields |
| `conversations.list` | Channely: id, name, is_private, is_archived, members | → `SlackChannel` (opt-in pro tracking) |
| `conversations.history` | Zprávy v channelu: ts, user, text, thread_ts, reactions, files | → `SlackMessage` |
| `conversations.replies` | Vlákno k parent ts | doplnění thread |
| `conversations.members` | Členové channelu | linkage |
| `chat.postMessage` | Poslat zprávu: channel, text, blocks (rich UI), thread_ts | sending API |
| `chat.update`, `chat.delete` | Editace zpráv | |
| `files.list`, `files.info` | Soubory v channelech | → `SlackFile` (reference, neukládáme obsah) |
| `reactions.get` | Reakce na zprávě | součást SlackMessage |
| `team.info` | Workspace metadata | → `SlackWorkspace` |

## Events API (real-time, doporučeno do budoucna)

Pro MVP **batch postačí**. Real-time přijde, až bude provoz vyšší.

- `message.channels`, `message.groups` — nová zpráva
- `reaction_added`, `reaction_removed`
- `user_change` — změna profilu (např. email)
- `team_join` — nový člen workspace

URL endpoint: `POST /api/slack/events` na Sentinex straně, ověření HMAC `signing_secret`.

## Datový model

```
SlackWorkspace (1 per workspace, shared schema)
├─ id (UUID)
├─ tenant_id (FK, nullable — SCB workspace nemá tenant)
├─ team_id (Slack workspace ID, např. "T03ABC")
├─ name, domain
├─ bot_token (encrypted), bot_user_id
├─ signing_secret (encrypted)
├─ installed_at, installed_by_user_id
└─ is_active

SlackChannel
├─ id (UUID)
├─ workspace_id (FK)
├─ slack_channel_id (e.g. "C03XYZ")
├─ name, purpose, topic
├─ is_private, is_archived
├─ is_tracked (opt-in flag)
├─ sync_from_ts (default last 30 days at first sync)
├─ member_count
└─ last_synced_at

SlackMessage
├─ id (UUID)
├─ channel_id (FK)
├─ ts (str, Slack timestamp — primary message ID)
├─ thread_ts (str, nullable)
├─ slack_user_id (str)
├─ person_id (FK identity.Person, nullable until resolver hits)
├─ text (raw)
├─ text_normalized (mentions resolved to names)
├─ mentioned_person_ids (UUID[], resolved)
├─ has_attachments (bool)
├─ reactions (JSONB)
├─ source_synced_at
├─ source_id = ts
└─ raw_payload (JSONB)
UNIQUE(channel_id, ts)

SlackSyncState
├─ channel_id (FK)
├─ last_ts, last_synced_at
└─ error_count, last_error

SlackFile (jen reference, neukládáme obsah)
├─ id, slack_file_id, channel_id, uploader_person_id
├─ name, mime_type, size, url_private, permalink
└─ source_synced_at
```

## Identity resolution flow

```
Slack user → PersonRecord(
  source_system=slack,
  email=user.profile.email,        ← klíčový pro link na existing Person z FAPI/Pipedrive
  full_name=user.real_name,
  slack_id=user.id,
) → IdentityResolver
```

Reverse: máme email z FAPI/Pipedrive → `users.lookupByEmail` → získáme slack_id → uložíme `PersonIdentity(slack_id)`.

## Sync strategie

### Init (one-time)
1. `users.list` → resolver pro každého → naplnění `PersonIdentity(slack_id)` pro SCB team.
2. `conversations.list` → seznam channelů, UI pro opt-in (sales-team, coaching-team, internal-dev…).
3. Pro opt-in channely: `conversations.history` od `oldest_ts = now - 30d` (nebo víc dle dohody) → uložit.
4. Thread replies přes `conversations.replies` pro každou zprávu s `thread_ts`.

### Periodic (Celery beat, 15 min)
- Pro každý opt-in channel: `conversations.history?oldest={last_ts}`.
- Update threads (jen pro zprávy z posledních 7 dní — staré thready se zřídka updatují).
- Uloží + update `SlackSyncState`.

### Real-time (později)
- Events API → webhook → uložit + trigger embedding job.

## Posílání zpráv z BR / Sentinexu

```
POST /api/slack/send  (interní endpoint Sentinexu)
{
  "to": {"person_id": UUID} | {"channel_id": "C03XYZ"} | {"email": "x@y.cz"},
  "text": "...",
  "blocks": [...]  # volitelně, Slack Block Kit
}
```

Sentinex:
1. Resolve `person_id` → `slack_id` z `PersonIdentity` → otevři DM přes `conversations.open`.
2. `chat.postMessage(channel=..., text=..., blocks=...)`.
3. Log do `slack_outbound_message` audit.

## Privacy & retention

- **DM nikdy nečteme** (žádný scope `im:history` pro bota).
- Pouze public a private channely, do kterých je bot pozván.
- Retention default 12 měsíců, dělá Celery beat job.
- GDPR: na žádost o výmaz → DELETE messages where person_id = X.

## Embedding & graph

- `SlackMessage` → embedding (filtr: text length > 30 chars, není bot, není emoji-only).
- Graphiti node `Message` s hranami `POSTED_BY(Person)`, `IN(Channel)`, `MENTIONS(Person)`, `IN_THREAD(Message)`.

## Otevřené body

- Které channely chceme tracket od dne 1? (#sales, #coaching, #ops, #dev?)
- Frekvence sync — 15 min stačí, nebo chceš near-real-time?
- Posílání z BR — má bot psát jménem konkrétního kouče, nebo univerzálně "Bryan"?
- Slack briefing — jak doručit (DM koučovi, channel `#briefings`, oba)?
