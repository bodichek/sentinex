# Prompt 12: Pilot Onboarding

## Goal

Onboard the first real pilot customer, polish rough edges discovered during onboarding, deliver the first real weekly brief, collect feedback.

## Prerequisites

- Prompts 1–11 complete
- Production deployed and stable
- Pilot customer identified, contacted, and committed
- Pilot customer has Google Workspace and is willing to connect

## Context

This is the moment of truth. Everything built so far gets tested against real-world use. Focus on pilot customer's experience, not feature addition.

## Constraints

- No new features — only polish, fix, stabilize
- Pilot CEO experience is paramount
- Incidents during pilot week are treated as P0

## Deliverables

1. **Onboarding checklist document** at `docs/ONBOARDING.md`:
   - Prerequisites for pilot (what they need to have ready)
   - Step-by-step procedure for operator (you) to onboard
   - Communication templates (welcome email, first brief intro)
   - Feedback collection template
2. **Tenant setup** for pilot customer:
   - Tenant created with correct schema name (company-safe identifier)
   - Domain `<pilot>.sentinex.<tld>` active
   - Owner account created, invited via email
   - Welcome email sent with credentials and onboarding link
3. **First user experience**:
   - Welcome landing page on first login
   - Guided setup: "Connect Google Workspace", "Invite team", "Configure Weekly Brief"
   - Clear copy (Czech) explaining what happens in each step
4. **Integration connection**:
   - Pilot CEO connects Google Workspace via OAuth
   - Initial sync runs
   - CEO sees confirmation that data is syncing
5. **Weekly Brief configuration**:
   - CEO sets recipients, schedule (Monday 07:00 their timezone)
   - CEO can preview a brief (manually triggered) before first scheduled one
6. **First scheduled brief delivery**:
   - Brief generates on Monday 07:00
   - Email arrives in CEO inbox
   - CEO can view in web UI
   - CEO can download PDF
7. **Polish items** (bug fixes and small improvements discovered during pilot):
   - Any error messages made user-friendly
   - Any confusing UI fixed
   - Performance issues addressed (e.g., slow queries)
8. **Monitoring setup for pilot**:
   - Sentry alert on errors for pilot tenant
   - Hetzner alert on resource spikes
   - Manual check daily for first week
9. **Feedback collection**:
   - 30-minute call with pilot CEO after first brief
   - Template questions:
     - First impression?
     - What was useful?
     - What was confusing?
     - Walk me through each section — valuable or not?
     - What's missing for this to be worth €4K/month?
     - Would you continue for 3 more months?
   - Notes documented
10. **Feedback incorporation**:
    - Issues categorized: P0 (blocker), P1 (important), P2 (nice-to-have)
    - P0 fixed within 48 hours
    - P1 fixed within 1 week
    - P2 added to backlog
11. **Post-pilot retrospective**:
    - What went well
    - What went badly
    - What to change for next pilot
    - Documented in `docs/retrospectives/pilot-1.md`

## Acceptance Criteria

- Pilot tenant fully set up and accessible
- Pilot CEO connected Google Workspace successfully
- First brief delivered by email (with content from real data)
- CEO read the brief (confirmed via conversation)
- Feedback session completed
- Critical feedback addressed
- Pilot running 7+ days without P0 incidents
- Retrospective documented

## Next Steps

After this prompt, MVP is complete. Next steps (out of scope):
- Second addon (Quarterly Planning Cockpit)
- Second integration (Microsoft 365)
- Second pilot customer
- Pricing and billing flow
- Marketing site and commercial launch

## Notes for Claude Code

- Don't over-engineer — this phase is about learning from pilot, not building
- Have a direct communication channel with pilot CEO (WhatsApp, Signal, Slack — whatever works)
- Log every pilot interaction in `docs/pilots/<pilot_name>/log.md`
- Be honest with pilot about MVP status — set expectations that things will break and be fixed quickly
- Offer to be on-call for the first 2 weeks of pilot
- Keep a "pilot feedback" Trello/Notion board with all items raised
- First brief might be underwhelming if data sparse — acknowledge this, explain it gets better
- If pilot wants a specific metric not in Insight Functions, add it quickly (this is exactly what feedback should drive)

## Risk Management

**Risk: Pilot has technical issue connecting Google Workspace**
- Mitigation: schedule onboarding call where you walk them through
- Fallback: test OAuth flow yourself first, document exact steps

**Risk: First brief has little useful data (low data quality)**
- Mitigation: manually prepare some KPIs beforehand
- Fallback: acknowledge in brief email that first brief is baseline; subsequent briefs will show trends

**Risk: Production incident during pilot week**
- Mitigation: keep deploy freeze during first week unless critical
- Fallback: rollback procedure ready, communicate transparently

**Risk: Pilot doesn't find value**
- Mitigation: ask specifically what they would find valuable, iterate
- Fallback: don't force it — better to learn what's missing than pretend

## Communication Templates

### Welcome Email

```
Subject: Vítejte v Sentinex — začínáme

Dobrý den,

vítejte v Sentinex. V příloze najdete přihlašovací údaje k platformě
a odkaz na první kroky onboardingu.

Během 30 minut se můžete přihlásit, připojit Google Workspace a nastavit
svůj první týdenní report. Pokud vám bude cokoli nejasné, jsem k dispozici.

Náš první společný hovor proběhne <datum>. Do té doby doporučuji projít
onboarding a zaznamenat si otázky.

S pozdravem,
<Jméno>
```

### First Brief Intro Email

```
Subject: Váš první týdenní report je připraven

Dobrý den,

v příloze tohoto mailu najdete svůj první týdenní strategický report.
Protože jde o první týden sbírání dat, některé sekce mohou být sparse —
s dalšími týdny se obraz zpřesní.

Rád bych si s vámi po přečtení promluvil (30 min). Zajímá mě:
- Co pro vás bylo užitečné?
- Co chybí?
- Jaké sekce byste chtěli vidět detailněji?

Domluvme si termín — stačí odpovědět na tento email.

S pozdravem,
<Jméno>
```
