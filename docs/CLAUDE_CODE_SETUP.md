# Claude Code — nastavení pro tento stroj

> **Stroj:** `/home/bodichek` (Linux, bash)
> **Účet:** brona.klus@gmail.com (claude.ai web)
> **Stav k:** 2026-05-13

---

## 1. Plugins (5/5 nainstalované a enabled)

| Plugin | Marketplace | Status | Zdroj |
| --- | --- | --- | --- |
| code-review | claude-plugins-official | ✓ enabled | anthropics/claude-plugins-official |
| context7 | claude-plugins-official | ✓ enabled | anthropics/claude-plugins-official |
| document-skills | anthropic-agent-skills (v f458cee31a75) | ✓ enabled | anthropics/skills |
| frontend-design | claude-plugins-official | ✓ enabled | anthropics/claude-plugins-official |
| superpowers (v5.1.0) | claude-plugins-official | ✓ enabled | anthropics/claude-plugins-official |

**Marketplaces (2):** `claude-plugins-official`, `anthropic-agent-skills`.

**Příkazy pro ověření:**
```bash
claude plugin list
claude plugin marketplace list
```

---

## 2. MCP servery

### 2.1 Remote (claude.ai web)
| Server | URL | Status |
| --- | --- | --- |
| Slack | https://mcp.slack.com/mcp | ✓ Connected |
| TODOIST | https://ai.todoist.net/mcp | ✓ Connected |
| Miro | https://mcp.miro.com | ✓ Connected |
| Google Calendar | https://calendarmcp.googleapis.com/mcp/v1 | ✓ Connected |
| Gmail | https://gmailmcp.googleapis.com/mcp/v1 | ✓ Connected |
| **Google Drive** | https://drivemcp.googleapis.com/mcp/v1 | ⚠ Needs authentication |

### 2.2 Plugin-provided
| Server | Command | Status |
| --- | --- | --- |
| plugin:context7 | `npx -y @upstash/context7-mcp` | ✓ Connected |

### 2.3 Lokální (per-machine, user scope)
| Server | Command | Status | Pozn. |
| --- | --- | --- | --- |
| filesystem | `npx -y @modelcontextprotocol/server-filesystem /home/bodichek/sentinex` | ✓ Connected | scope: Sentinex repo |
| playwright | `npx -y @playwright/mcp@latest` | ✓ Connected | browser automation |
| supabase | `npx -y @supabase/mcp-server-supabase` | ✓ Connected | **token = placeholder, doplnit** |
| serena | `uvx --from git+https://github.com/oraios/serena serena start-mcp-server` | ✓ Connected | semantic code intelligence |

**Příkaz pro ověření:** `claude mcp list`

---

## 3. Nástroje na stroji

| Nástroj | Cesta | Verze |
| --- | --- | --- |
| `claude` (CLI) | `/home/bodichek/.npm-global/bin/claude` | – |
| `uv` / `uvx` | `/home/bodichek/.local/bin/{uv,uvx}` | 0.11.14 |
| Node `npx` | systémový | – |

> `~/.local/bin` zatím není v PATH automaticky — pro shell použití přidej do `~/.bashrc`:
> ```bash
> echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
> ```

---

## 4. Settings — `~/.claude/settings.json`

```json
{
  "enabledPlugins": {
    "context7@claude-plugins-official": true,
    "frontend-design@claude-plugins-official": true,
    "code-review@claude-plugins-official": true,
    "document-skills@anthropic-agent-skills": true,
    "superpowers@claude-plugins-official": true
  },
  "extraKnownMarketplaces": {
    "anthropic-agent-skills": {
      "source": { "source": "github", "repo": "anthropics/skills" }
    }
  },
  "effortLevel": "low",
  "autoUpdatesChannel": "latest",
  "theme": "dark"
}
```

MCP servery (lokální) jsou uloženy v `~/.claude.json` (spravované přes `claude mcp add/remove`).

---

## 5. Skills (zpřístupněné přes pluginy)

Pluginy `document-skills` + `superpowers` přinášejí skill suite:

**Document skills:** web-artifacts-builder, pptx, pdf, canvas-design, mcp-builder, claude-api, algorithmic-art, webapp-testing, skill-creator, internal-comms, theme-factory, frontend-design, brand-guidelines, slack-gif-creator, doc-coauthoring, xlsx, docx.

**Superpowers:** writing-plans, using-git-worktrees, verification-before-completion, requesting-code-review, executing-plans, subagent-driven-development, brainstorming, receiving-code-review, test-driven-development, using-superpowers, systematic-debugging, dispatching-parallel-agents, writing-skills, finishing-a-development-branch.

**Code-review:** code-review (slash command + agent).

**Frontend-design:** frontend-design skill.

---

## 6. ⚠ Co zbývá udělat ručně (interaktivní akce)

| # | Akce | Jak |
| --- | --- | --- |
| 1 | **Google Drive auth** | V Claude Code: `/mcp` → vyber Google Drive → projít OAuth |
| 2 | **GitHub MCP** (není zatím připojen) | `/mcp` → přidej GitHub server přes OAuth |
| 3 | **Supabase access token** | `claude mcp remove supabase` && `claude mcp add -s user supabase -e SUPABASE_ACCESS_TOKEN=sbp_xxx -- npx -y @supabase/mcp-server-supabase` |
| 4 | **PATH pro `uv`/`uvx`** | `echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc` (jen pro shell, MCP už používá absolutní cestu) |
| 5 | **Restart Claude Code** | Po instalaci pluginů, aby se načetly skills do session |

---

## 7. ❌ Chybí oproti referenčnímu nastavení

| Co | Stav | Důvod |
| --- | --- | --- |
| GitHub MCP (OAuth) | chybí | vyžaduje interaktivní `/mcp` přihlášení |
| Supabase token | placeholder | uživatel doplní vlastní token |
| Google Drive auth | needs auth | vyžaduje OAuth přes `/mcp` |
| `/login` na claude.ai | implicitně OK | claude.ai MCP servery už připojené |

---

## 8. Doporučení pro nové projekty

V projektech, které **nejsou** Sentinex / Django, **nepřebírej** `.claude/settings.local.json` z tohoto repa. Obsahuje allowlisty specifické pro Sentinex:
- `Bash(poetry:*)`, `Bash(pytest:*)`, `Bash(python manage.py:*)`
- Docker Compose / migrate příkazy
- Django-specific helpers

V novém projektu si je přidávej přes `/permissions` nebo Allow tlačítka podle reálné potřeby.

---

## 9. Užitečné příkazy

```bash
# Plugins
claude plugin list
claude plugin install <name>@<marketplace>
claude plugin marketplace add <github-repo>

# MCP
claude mcp list
claude mcp add -s user <name> -- <command...>
claude mcp add -s user <name> -e KEY=val -- <command...>
claude mcp remove <name>

# Verifikace v session
/plugin
/mcp
/skills
```

---

*Připraveno: Claude na základě setup-session 2026-05-13 | Sentinex / brona.klus*
