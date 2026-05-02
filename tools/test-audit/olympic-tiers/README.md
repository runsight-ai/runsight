# Olympic Test Cleanup Tiers

This directory turns `tools/test-audit/full-test-cleanup-map.tsv` into execution
tiers. The goal is to refactor the test suite without repeating the previous
failure mode: no endless surgical wandering, no stale partial counts, and no
new one-off tests per cleanup ticket.

## Why Tiers

The tier model makes sense because test cleanup has different risk classes:

- deleting a temporary source-scan guard is low risk
- merging duplicated suites is medium risk
- shrinking browser/integration matrices is higher risk
- splitting god suites and deep isolation fixtures is highest risk

We should run one tier, validate it, refresh the audit, and only then promote
the next tier. If a tier reveals new duplication or missing owners, those files
move into the next tier rather than being patched ad hoc.

## Tier Files

| Tier | File | Action | Count |
|---|---|---|---:|
| 1 Bronze | `tier-1-bronze-delete.tsv` | Delete cleanup/migration residue | 51 |
| 2 Silver | `tier-2-silver-merge-then-delete.tsv` | Merge unique coverage into owner suites, then delete duplicates | 135 |
| 3 Silver | `tier-3-silver-move-to-tooling.tsv` | Move durable governance to tooling or delete temporary guards | 22 |
| 4 Gold | `tier-4-gold-shrink-to-smoke.tsv` | Shrink broad suites to high-value smoke coverage | 72 |
| 5 Gold | `tier-5-gold-split-god-suites.tsv` | Split mixed-concern god suites into behavior owners | 75 |
| 6 Platinum | `tier-6-platinum-externalize-fixtures.tsv` | Externalize inline fixtures into owning workspaces | 44 |
| 7 Diamond | `tier-7-diamond-deep-review.tsv` | Resolve blockers and high-risk infrastructure | 6 |

Regenerate tier files after the audit map changes:

```bash
uv run python tools/test-audit/build_olympic_tiers.py
```

Regenerate current inventory after each tier:

```bash
uv run python tools/test-audit/collect_inventory.py
```

## Execution Gate

Each tier runs through this RGB-shaped loop:

1. Green workers make scoped cleanup changes from the tier TSV.
2. Blue reviewers validate mechanical safety: no lost behavior, targeted tests
   pass, no fixture/runtime-state violations, no full-suite runs.
3. Yellow reviewers validate intent: the cleanup achieved the audit row's
   target, no new mirrors/governance residue, and owner suites are real.
4. Post-tier auditors refresh the test map and classify any newly exposed
   candidates into the next tier.

No worker should run full pytest, full vitest, or full Playwright. Use targeted
commands from the audit rows and keep browser/API tests single-worker where
relevant.

## Sharding Rule

Shard by workspace and behavior cluster, not by arbitrary line count:

- API: domain/data/logic/transport/unit
- Core: assertions/parser/runtime/isolation/blocks/dispatch/governance
- GUI: api/dashboard/runs/settings/souls/surface/routes/utils
- E2E: canvas/settings/runs/souls/subflows/governance
- UI/shared/tools: contracts/tokens/stories/governance

Within one tier, workers must own disjoint write scopes. Blue and Yellow may
review overlapping scopes, but Green workers must not edit the same file family
in parallel.
