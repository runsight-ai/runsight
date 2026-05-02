# Tier 3 Silver: Move Durable Governance To Tooling

Use this prompt for Green workers assigned rows from
`tools/test-audit/olympic-tiers/tier-3-silver-move-to-tooling.tsv`.

```text
You are a Green worker in the Runsight test cleanup RGB pipeline.

Scope:
- Work only on assigned MOVE_TO_TOOLING rows.
- Own the listed app/package governance files plus the new or existing tooling
  governance owner.

Goal:
- App/package tests should test app/package behavior.
- Durable repo/source governance belongs in `tools/tests` or a shared tooling
  scanner.
- Temporary migration guards should be deleted, not moved.

Rules:
- First decide: durable policy or temporary cleanup residue.
- If durable, move the rule into a small tooling-owned governance suite.
- If temporary, delete it and document the owner behavior that makes it safe.
- Do not leave duplicate governance in both locations.
- Do not scan runtime/user state or `custom/`. Static scans must stay in source
  and test workspaces only.
- Do not run full pytest/vitest/playwright.

Verification:
- Run the moved tooling test only:
  `uv run pytest tools/tests/<target>.py -q`
- Run targeted owner behavior tests if source governance was replaced by
  behavior coverage.

Final output:
- Files moved or deleted.
- Tooling owner created/updated.
- Temporary rules intentionally expired.
- Targeted commands run and results.
- Impact Evidence for source tree boundaries checked.
```
