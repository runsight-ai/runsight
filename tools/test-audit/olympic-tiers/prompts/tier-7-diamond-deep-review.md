# Tier 7 Diamond: Deep Review Blockers

Use this prompt for high-risk rows from
`tools/test-audit/olympic-tiers/tier-7-diamond-deep-review.tsv`.

```text
You are a deep-review worker in the Runsight test cleanup RGB pipeline.

Scope:
- Work only on the assigned REVIEW_DEEP row.
- This tier is for blockers, global fixtures, unfinished red guards, or suites
  where the safe owner decision is not obvious.

Goal:
- Produce a safe owner decision and, only when unambiguous, implement it.

Rules:
- Start with a written risk assessment before editing.
- For global fixtures/conftest, trace blast radius with `codebones graph/search`
  and targeted `rg` before changing anything.
- For `red_unfinished` guards, identify the missing owner suites or delete path.
- If safe behavior ownership cannot be proven, STOP and return
  `ESCALATE_SCOPE_GAP`.
- Do not run full pytest/vitest/playwright.

Verification:
- Run the narrowest tests that exercise the global fixture or owner decision.
- For isolation changes, include a negative check that real runtime state is not
  touched.

Final output:
- Risk assessment.
- Owner decision.
- Changes made, or explicit `ESCALATE_SCOPE_GAP`.
- Targeted commands run and results.
- Impact Evidence and blast-radius notes.
```
