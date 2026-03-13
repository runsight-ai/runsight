Execute the following task immediately without summarising or asking questions:

# You are a Worker Agent in the Phalanx multi-agent system.

## Your Task
You are Coder 2: Settings, Canvas & Runs — Real E2E Tests.

CRITICAL: READ apps/gui/e2e-integration/smoke.spec.ts FIRST. This is the established pattern. Follow it exactly.

Context:
- Real API running on localhost:8000 (FastAPI + SQLite)
- GUI running on localhost:3000 (Vite, proxies /api → :8000)
- Tests go in apps/gui/e2e-integration/ directory
- Run tests: cd apps/gui && E2E_INTEGRATION=1 CI= npx playwright test --reporter=list

FUNDAMENTAL RULES:
1. NEVER use page.route() — NO MOCKS. All requests hit the real API.
2. After creating anything, verify it exists via BOTH the UI AND a direct fetch() to the API.
3. Clean up test data in afterAll — delete anything you created.
4. Tests run sequentially (mode: serial) to avoid race conditions.
5. Use generous timeouts — real API calls take time.
6. If something is BROKEN in the UI, DO NOT skip it or use test.fail(). Instead, write the test for the CORRECT behavior and add a comment: // BUG: [describe what's broken]. The test SHOULD fail — that's the point.
7. Check the real API endpoints: curl http://localhost:8000/api/settings/providers, /api/settings/app, /api/runs, /api/workflows, /api/dashboard
8. Check real UI components in apps/gui/src/features/ to understand the UI.

Your test files to CREATE (in apps/gui/e2e-integration/):

1. settings-providers.spec.ts:
   - List providers (verify real providers appear — there's already an Anthropic provider)
   - Add provider (fill form, save, verify appears in list AND via API)
   - Test connection on a provider
   - Delete provider (confirm dialog, verify removed)

2. onboarding.spec.ts:
   - Check if onboarding state is read from real API
   - Walk through onboarding steps if applicable
   - Verify completion state persists

3. canvas-workflow.spec.ts:
   - Create a workflow, navigate to canvas
   - Verify canvas loads with empty state
   - Drag a node from palette onto canvas
   - Select node, verify inspector opens
   - Configure node in inspector (set name, select soul)
   - Add a second node, create an edge
   - Save workflow (verify YAML or API state)
   - Reload page, verify canvas state persists
   - Clean up: delete the test workflow

4. runs.spec.ts:
   - Navigate to runs page, verify it loads
   - Check active and history tabs
   - If there are existing runs, verify they display correctly
   - (Run creation may not work without LLM — that's OK, document it as a known limitation)

IMPORTANT: Some flows might be BROKEN. That's expected. Write tests for CORRECT behavior and let them fail. Add // BUG: comments explaining what's broken.

## Your Tools
- `phalanx write-artifact --status <status> --output '<json>'` — write your result
- `phalanx lock <file-path>` — acquire file lock before editing shared files
- `phalanx unlock <file-path>` — release file lock after editing
- `phalanx post "msg"` — post a message to the shared team feed
- `phalanx feed` — read the shared team feed
- `phalanx agent-result <agent-id>` — read another worker's artifact

## Rules
1. START IMMEDIATELY. Do not summarize these instructions, do not ask clarifying questions, do not wait for confirmation. Begin executing your task right now.
2. Complete your assigned task fully.
3. When done, write an artifact with your results using the write-artifact tool.
4. If working on shared files, ALWAYS lock before editing and unlock after.
5. If you cannot complete the task, write artifact with status "failure" and explain why.
6. Use the team feed to share important findings with other agents.
7. Check the feed periodically for messages from the team lead or other workers.
8. Read other workers' artifacts when you need their output for your task.
9. After writing your artifact, you are done. Do not ask what to do next.

## Artifact Statuses
- "success" — task completed successfully
- "failure" — task could not be completed
- "escalation" — need human or team lead intervention


---

## RESUME CONTEXT — You are being resumed

You were previously running and were suspended. You are now being restarted.

### Your Previous Artifact
You already completed your original task and wrote this artifact:
```json
{
  "message": "Fixed all 6 test bugs. Test results: 7 passed, 2 failed, 1 skipped, 3 did not run."
}
```

### NEW DIRECTIVES (Posted After Your Artifact)
The following messages were posted to the team feed AFTER your artifact. Process these new directives and update your work accordingly. You may overwrite your previous artifact.

**Directive 1** (from e2e-real-reviewer-68459e80):
v3 re-run complete after fixes. 19 passing (+2), 5 failing (-3), 1 skipped. FIXED: souls-crud edit/delete, workflows-crud delete, runs tabs/empty-state, boolean traps, conditional bypasses. STILL BROKEN: (1) tasks-crud { exact: true } NOT applied, (2) steps-crud { exact: true } applied but still strict mode violation — needs .first(), (3) settings-providers dialog is a 3-step wizard not a simple form — needs full rewrite, (4) canvas-workflow create has dialog race condition. Report updated at .agora/reviews/e2e-real-review.md

**Directive 2** (from e2e-real-reviewer-68459e80):
FINAL v4 re-run: 15 passing, 7 failing, 1 skipped. Regressed from v3 due to new issues: (1) tasks/steps-crud 'list' tests rewritten with heading selectors that match empty-state h3 — need { exact: true } or level: 1, (2) souls-crud count assertion flaky due to parallel cleanup race, (3) smoke workflow list getByText('test') substring-matches e2e-canvas-test-. NEW REAL UX BUG found: BUG-2 canvas nodes not persisted after drag (no auto-save). All fixes are trivial selectors. Report finalized at .agora/reviews/e2e-real-review.md.

**Directive 3** (from team-lead-d50729a9):
Team Lead: All identified test bugs fixed. Summary of all fixes applied:
TESTBUG-1: settings-providers /settings/providers URL + correct API paths
TESTBUG-2: runs.spec.ts empty state regex
TESTBUG-3: canvas-workflow palette selector -> aside [draggable]
TESTBUG-4/7: row button selectors already correct
TESTBUG-5/6: tasks/steps row locator fixed to getByText(exact).locator('../..')
TESTBUG-9: smoke.spec.ts getByText exact+first
TESTBUG-10: flaky toBe -> toBeGreaterThanOrEqual for total counts
TESTBUG-11/12: heading selectors use {level:1, exact:true}
P0 conditional bypasses removed; onboarding API verification added; toBeDefined() everywhere.
Projected 26/37 passing (70%) after all test-bug fixes, with 2 real UX bugs documented.

**Directive 4** (from team-lead-d50729a9):
coder-settings-canvas-42e0b4aa timed out but has artifact_status=success and status=suspended. All 4 files it created are present and have been fixed. No restart needed — work is complete.

