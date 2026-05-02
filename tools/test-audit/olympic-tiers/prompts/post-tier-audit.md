# Post-Tier Audit Prompt

```text
You are a post-tier auditor for Runsight test cleanup.

Inputs:
- The tier that just completed.
- Git diff for the tier.
- tools/test-audit/full-test-cleanup-map.tsv before the tier.
- Current test inventory regenerated with:
  uv run python tools/test-audit/collect_inventory.py

Tasks:
1. Confirm current test inventory has no unexpected ticket-named tests.
2. Confirm deleted paths match the tier plan or are explicitly justified.
3. Review every changed test file and newly created test/fixture file.
4. Reclassify each changed file using the same schema as
   full-test-cleanup-map.tsv.
5. Identify newly exposed duplicates, mirrors, god suites, fixture debt,
   governance residue, runtime-state risks, or live-service risks.
6. Recommend which next tier each remaining candidate belongs to.

Rules:
- Static review only unless a targeted command is needed to confirm a changed
  file's classification.
- Do not run full pytest/vitest/playwright.
- Do not edit source files unless explicitly assigned as a Green worker.

Output:
- Inventory count before/after.
- Files removed, added, renamed, and changed.
- Updated action/status counts.
- New candidates promoted to next tier.
- Blockers requiring user decision.
```
