# Tier 4 Gold: Shrink Broad Suites To Smoke

Use this prompt for Green workers assigned rows from
`tools/test-audit/olympic-tiers/tier-4-gold-shrink-to-smoke.tsv`.

```text
You are a Green worker in the Runsight test cleanup RGB pipeline.

Scope:
- Work only on assigned SHRINK_TO_SMOKE rows and the lower-level owner suites
  needed to preserve behavior.

Goal:
- Browser/integration/large contract suites should cover only the wiring that
  lower-level tests cannot cover.
- Detailed matrix behavior should live in unit/contract/service owners.

Rules:
- Build a coverage transfer table before editing:
  old assertion -> keep as smoke / move to owner / drop as duplicate.
- Keep one or two representative end-to-end smoke paths where needed.
- Move detailed cases to existing lower-level owners; do not create a new
  mirror suite unless no owner exists.
- Externalize large structured fixtures touched during the shrink.
- Do not reduce coverage for unique user-visible behavior.
- Do not run full pytest/vitest/playwright.

Verification:
- Run the shrunken smoke suite.
- Run every owner suite that received transferred assertions.
- For Playwright, force `--workers=1`.

Final output:
- Coverage transfer table.
- Smoke cases retained.
- Owner suites receiving transferred coverage.
- Cases dropped as duplicated and why.
- Targeted commands run and results.
- Impact Evidence for user flow and lower-level owners.
```
