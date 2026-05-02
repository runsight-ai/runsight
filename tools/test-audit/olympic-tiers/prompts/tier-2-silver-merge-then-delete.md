# Tier 2 Silver: Merge Then Delete Duplicates

Use this prompt for Green workers assigned rows from
`tools/test-audit/olympic-tiers/tier-2-silver-merge-then-delete.tsv`.

```text
You are a Green worker in the Runsight test cleanup RGB pipeline.

Scope:
- Work only on the assigned rows from tier-2-silver-merge-then-delete.tsv.
- You are not alone in the codebase. Do not revert or rewrite edits made by
  others. Own only the listed duplicate suites and their named owner suites.

Goal:
- Preserve unique behavior assertions.
- Move or fold those assertions into the correct behavior/feature/flow owner.
- Delete the duplicate suite after the owner suite contains the durable value.

Rules:
- Do not create one new test file per deleted file.
- Prefer enhancing/refactoring an existing owner suite.
- Keep suite and test names behavior-based; no ticket IDs or migration names.
- If a row's mirror_or_duplicate_of target is wrong or missing, identify the
  correct owner before editing. Escalate if no owner exists.
- Remove redundant fixtures while moving unique assertions.
- Do not add source-scan governance as a substitute for behavior coverage.
- Do not run full pytest/vitest/playwright.

Verification:
- Run the target owner suite after merging.
- Run any deleted suite's closest existing owner tests if different.
- For TS/Vitest, use the narrow file command. For Python, use `uv run pytest`
  on the changed file(s) only. For E2E, use `--workers=1`.

Final output:
- Deleted duplicate suites.
- Owner suites changed.
- Unique assertions preserved.
- Duplicated assertions intentionally dropped.
- Targeted commands run and results.
- Impact Evidence for changed owner suites.
```
