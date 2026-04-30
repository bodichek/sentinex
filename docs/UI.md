# UI / Design System

Sentinex ships a single-style futuristic interface — dark, glass-morphic,
with cyan/violet neon accents. The whole system lives inline in
`templates/base.html` (CSS variables + utility classes prefixed with
`sx-`), Tailwind v4 is loaded via the browser CDN for layout utilities,
and Inter / JetBrains Mono come from Google Fonts.

There is no separate stylesheet pipeline yet. Adding one is a follow-up,
but the inline approach is intentional for the MVP: the design tokens
sit in one place and every template imports them automatically through
`base.html`.

## Design tokens

```css
--sx-bg-0       #07070f   /* deepest background */
--sx-bg-1       #0c0d1c   /* page background gradient end */
--sx-panel      rgba(255,255,255,0.04)  /* glass surface */
--sx-panel-strong rgba(255,255,255,0.08)
--sx-border     rgba(148,163,184,0.14)
--sx-text       #e6e8ee
--sx-text-dim   #94a3b8
--sx-text-mute  #64748b
--sx-accent     #00e5ff   /* primary — cyan */
--sx-accent-2   #a78bfa   /* secondary — violet */
--sx-accent-3   #34d399   /* tertiary — emerald */
--sx-success    #4ade80
--sx-warning    #fbbf24
--sx-danger     #f87171
```

Backgrounds use radial gradients of the two accents fading into the
deep navy base — gives the whole app a subtle "hologram" feel without
costly imagery.

## Component classes

| Class | Purpose |
|---|---|
| `.sx-glass` | Translucent panel with backdrop-blur. Use for cards, navbars, header tiles. |
| `.sx-glass-strong` | Heavier glass — modal-like surfaces, install wizards. |
| `.sx-h1` | Gradient-filled page heading (white → cyan → violet). |
| `.sx-btn` | Base button. Pair with `sx-btn-primary` (neon CTA), `sx-btn-ghost` (transparent), `sx-btn-danger`. |
| `.sx-input` | Form field — dark with focus halo in `--sx-accent`. |
| `.sx-pill`, `.sx-pill-on/-warn` | Status chips (Active / Setup / Warning). |
| `.sx-tile`, `.sx-tile-icon` | Connector grid tile + icon slot. |
| `.sx-step`, `.sx-step-dot`, `.sx-step.active`, `.sx-step.done` | Wizard step rail (Google-consent-style). |
| `.sx-side-link[.active]` | Sidebar nav row in `app_shell.html`. |
| `.sx-mono`, `.sx-code` | JetBrains Mono utility + inline code chip. |
| `.sx-pulse` | 1.6 s animated halo on status dots. |

## Connector UI conventions

The integrations grid (`templates/integrations/list.html`) uses a single
`connectors/_tile.html` partial. Every connector tile shows:

1. **Brand icon** — SVG inline from `connectors/_icons.html`. Add new
   providers there; pass `icon="<provider>"` to the include.
2. **Name + status pill** — pulled from the `Integration` row.
3. **One-line description** + auth badges (e.g. `OAuth 2.0`,
   `Basic Auth`, `MCP · OAuth 2.1 + PKCE`).
4. **Connect / Setup CTA** — primary neon button. Method is `post`
   for OAuth flows (start state generation in the view) and `get` for
   paste-token wizards (no side-effect on click).
5. **Disconnect** — red ghost button + `last_sync_at` next to it when
   the integration is active.

### Setup wizards (Google-consent style)

Each connector that uses paste-token auth (SmartEmailing, Trello) has a
dedicated full-page wizard at `/integrations/<provider>/setup/`. The
shape is always:

1. **Header card** — connector icon, name, status pill, "where data
   lives" disclaimer (encrypted in DB, never `.env`).
2. **Scope panel** — "Sentinex bude moci…" bullet list (mirrors what a
   Google OAuth consent screen shows).
3. **3 steps**:
   - Where to find the credential in the upstream app (with deep link).
   - How to generate the API key / token.
   - Form to paste the values, with `Uložit a ověřit` button that
     pings the upstream API before activating the integration.

OAuth-based connectors (Slack, Pipedrive, Canva, Google Workspace) do
**not** need a wizard page — clicking the tile redirects straight to
the upstream consent screen. The post-callback success returns to the
integrations list, which now shows the green Active pill.

## Where credentials live

Per CLAUDE.md security rules, **no user-entered credential is written to
`.env`**. The `.env` file holds only platform-level OAuth client_id /
client_secret pairs (one Slack app, one Pipedrive app, one Canva app —
shared across all tenants). Per-tenant secrets — paste tokens, OAuth
access/refresh tokens, API keys — are encrypted with Fernet inside
`apps.data_access.models.Credential.encrypted_tokens` and isolated by
tenant schema (django-tenants).

This is what makes `.env` a deploy artefact (read-only, set by ops) and
keeps the app process unable to mutate it from a request handler.

## Adding a new connector to the UI

1. Add an SVG branch in `templates/connectors/_icons.html` keyed on
   the provider string used in `Integration.provider`.
2. Add a tile include in `templates/integrations/list.html` with
   `provider`, `provider_name`, `provider_subtitle`, `connect_url`,
   `connect_method` and a short `badges` string.
3. If the connector uses a paste flow, copy
   `templates/connectors/smartemailing_setup.html` as the starting
   point — keep the 3-step structure, replace icon + copy + form
   fields, and point the form `action` at your `save_credentials`
   view.
4. If the connector uses OAuth, no wizard page is needed — the tile's
   POST button starts the consent flow.

## Roadmap

- Move CSS out of `base.html` once we add a real asset pipeline (Tailwind
  CLI build) — keep token names stable to avoid template churn.
- Per-tenant theme override (logo + accent) — one extra row on `Tenant`.
- Empty-state illustration set + onboarding tour after first login.
- Accessibility audit (focus ring on `.sx-tile` keyboard nav, contrast
  ratios on `--sx-text-mute`, prefers-reduced-motion for `.sx-pulse`).
