# Phase 4: Pilot & Polish (Week 4)

## Goal

Prepare Sentinex for its first real pilot customer. Polish rough edges, ensure stability, onboard a pilot tenant, deliver the first real weekly brief.

## Prerequisites

- Phases 1–3 complete
- Pilot customer identified and committed
- Pilot customer has a Google Workspace account ready to connect

## Reference Materials

- All `docs/` files
- `.claude/skills/deploy.md`
- `.claude/skills/debug-tenant.md`

## Deliverables

By end of Phase 4:

1. **Pilot tenant fully onboarded**
   - Tenant created
   - Users invited (CEO + 1-2 additional)
   - Google Workspace connected
   - Weekly brief configured
   - First brief successfully delivered
2. **Production environment stable**
   - All migrations applied
   - Monitoring (Sentry, Hetzner) reporting normally
   - Backups verified (when set up)
   - SSL certificates valid
3. **Error handling polished**
   - Graceful degradation when data missing
   - User-friendly error messages
   - Clear onboarding flow
4. **Documentation complete**
   - All `docs/` current
   - Pilot onboarding procedure documented
5. **Performance baseline**
   - Weekly brief generation under 60 seconds
   - Query response under 20 seconds
   - Dashboard load under 2 seconds
6. **Final tests pass**
   - All integration tests
   - End-to-end flow tested with real data
   - Tenant isolation verified
7. **Pilot feedback incorporated**
   - Collected feedback from pilot CEO
   - Critical issues addressed
   - Improvement backlog documented

## Constraints

- No new features in this phase — only polish, fix, stabilize
- Pilot customer experience is paramount
- Don't break existing functionality

## Step-by-Step Breakdown

### Step 4.1: Deployment Hardening

Finalize production deployment, monitoring, backups (basic).

See: `prompts/11-deployment.md`

### Step 4.2: Pilot Onboarding

Onboard first real customer, deliver first brief, collect feedback.

See: `prompts/12-pilot-onboarding.md`

## Acceptance Criteria

Phase 4 is complete when:

1. **Pilot onboarded**: tenant, users, integrations all configured
2. **First brief delivered**: actual email sent to real CEO with real data
3. **Feedback collected**: at least one feedback session with pilot
4. **No critical bugs**: all Sentry errors resolved or triaged
5. **Monitoring working**: can observe system health
6. **Documentation complete**: any new procedure documented
7. **Sprint review**: retrospective completed, next steps identified

## What NOT to Do in Phase 4

- Don't add new features
- Don't refactor code unless blocking pilot
- Don't start second pilot (sequential, not parallel)
- Don't scale to multiple tenants until first pilot successful

## Verification

End of Phase 4 milestone:

- [ ] Pilot tenant can log in
- [ ] Pilot tenant has Google Workspace connected
- [ ] First weekly brief delivered by email
- [ ] Pilot CEO read the brief
- [ ] Feedback session completed
- [ ] Critical issues fixed
- [ ] System running on production for at least 7 days with no critical incidents

## Estimated Effort

- **Time**: 3–5 days working 8–16 hours each (fewer coding hours, more ops/communication)
- **Coding**: ~500–1000 lines (mostly bug fixes and polish)
- **Non-coding**: onboarding calls, documentation, feedback sessions

## Post-MVP Roadmap

After Phase 4 success, the next phases (not in MVP scope):

**Phase 5: Second Addon**
- Build Quarterly Planning Cockpit or Cash Flow Dashboard
- Expand Insight Functions

**Phase 6: Second Integration**
- Add Microsoft 365 MCP or Slack MCP
- Expand data sources

**Phase 7: Second Pilot**
- Onboard second customer
- Test multi-tenant at real load

**Phase 8: Commercial Launch**
- First paid customer
- Billing flow
- Marketing site

## Questions to Ask Before Starting

- Who is the pilot customer? (Name, role, company)
- When is the onboarding call scheduled?
- What are the specific expectations of the pilot?
- Is there a written pilot agreement?

## Risk Factors

- **Pilot backs out**: have a fallback customer or internal test tenant
- **Pilot data is too sparse**: first brief might be underwhelming — set expectations
- **Critical bug during pilot**: have rollback plan ready
- **Pilot feedback is negative**: listen, understand, don't over-promise fixes

## Success Metrics

Quantitative:
- First brief delivered: Yes/No
- Brief read by CEO: Yes/No
- Critical errors during pilot week: <= 1
- Response time for pilot-reported issues: < 24 hours

Qualitative:
- Pilot CEO finds the brief useful (self-reported)
- Pilot willing to continue using and pay for it
- Clear understanding of what's missing for full commercial product

## Feedback Session Template

Schedule 60-minute call with pilot CEO after first brief:

1. **First 15 min**: Their experience
   - What did you notice first?
   - What was useful?
   - What was confusing?

2. **Next 20 min**: Deep dive on brief content
   - Walk through each section
   - Which sections are valuable?
   - Which sections should be removed or expanded?

3. **Next 15 min**: Their expectations
   - What would make you pay €4K/month for this?
   - What features are missing?
   - What else would you want to see?

4. **Last 10 min**: Next steps
   - Continue using for 4 more weeks?
   - Convert to paid?
   - Specific improvements needed?

Document all feedback in a shared Google Doc. Prioritize issues: P0 (blocker), P1 (important), P2 (nice-to-have).

## Handoff to Ongoing Operations

After Phase 4, Sentinex enters ongoing operations mode:
- Weekly reviews with pilot customer
- Bi-weekly feature releases
- Ongoing product development per pilot feedback
- Start outreach to second pilot after 4 weeks with first pilot
