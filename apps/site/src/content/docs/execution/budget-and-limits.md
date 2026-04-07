---
title: Budget & Limits
description: Cost caps, token caps, timeouts, and warn/kill modes — the limits YAML section for workflow and block-level budget enforcement.
---

The `limits` section controls how much a workflow or individual block is allowed to spend in cost, tokens, and wall-clock time. When a limit is breached, the engine either kills execution immediately or emits a warning and continues, depending on the `on_exceed` mode.

:::caution
Budget enforcement is backend-only. There is no frontend UI for configuring or visualizing limits yet. You set limits directly in the workflow YAML.
:::

## Workflow-level limits

Add a `limits` section at the top level of your workflow YAML:

```yaml title="custom/workflows/research-pipeline.yaml"
version: "1.0"
limits:
  cost_cap_usd: 2.50
  token_cap: 100000
  max_duration_seconds: 300
  on_exceed: fail
  warn_at_pct: 0.8
workflow:
  name: research-pipeline
  entry: step_one
blocks:
  step_one:
    type: linear
    soul_ref: analyst
```

### WorkflowLimitsDef fields

| Field | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `cost_cap_usd` | `float?` | `None` | `>= 0.0` | Maximum total LLM cost in USD |
| `token_cap` | `int?` | `None` | `>= 1` | Maximum total tokens (prompt + completion) |
| `max_duration_seconds` | `int?` | `None` | `1 -- 86400` | Wall-clock timeout for the entire workflow |
| `on_exceed` | `"warn" \| "fail"` | `"fail"` | --- | What happens when a cap is breached |
| `warn_at_pct` | `float` | `0.8` | `0.0 -- 1.0` | Percentage threshold for early warning events |

All fields are optional. If you omit `limits` entirely, no budget enforcement is applied.

## Per-block limits

Individual blocks can have their own `limits` section:

```yaml title="custom/workflows/research-pipeline.yaml"
blocks:
  expensive_step:
    type: linear
    soul_ref: analyst
    limits:
      cost_cap_usd: 1.00
      token_cap: 50000
      max_duration_seconds: 120
      on_exceed: fail
```

### BlockLimitsDef fields

| Field | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `cost_cap_usd` | `float?` | `None` | `>= 0.0` | Maximum LLM cost for this block |
| `token_cap` | `int?` | `None` | `>= 1` | Maximum tokens for this block |
| `max_duration_seconds` | `int?` | `None` | `1 -- 86400` | Wall-clock timeout for this block |
| `on_exceed` | `"warn" \| "fail"` | `"fail"` | --- | What happens when a cap is breached |

:::note
Block-level limits do **not** have a `warn_at_pct` field. Only workflow-level limits support the warning threshold.
:::

## Warn mode vs kill mode

The `on_exceed` field controls what happens when a budget cap is breached:

### Kill mode (`on_exceed: "fail"`)

The default. When any cap is exceeded, the engine raises a `BudgetKilledException` immediately. The run terminates with `status: failed` and `fail_reason: "budget_exceeded"`. The exception includes structured metadata:

- `scope` --- `"block"` or `"workflow"`
- `block_id` --- which block triggered the breach (if block-scoped)
- `limit_kind` --- `"cost_usd"`, `"token_cap"`, or `"timeout"`
- `limit_value` --- the configured cap
- `actual_value` --- the value that exceeded the cap

### Warn mode (`on_exceed: "warn"`)

When a cap is exceeded, the engine logs a warning but execution continues. The run can finish normally even after exceeding a budget cap. Use this for soft budgets where you want visibility but not hard stops.

```yaml title="Warn mode example"
limits:
  cost_cap_usd: 1.00
  on_exceed: warn
  warn_at_pct: 0.8
```

With this configuration, a warning event is emitted at 80% of the cost cap ($0.80), and another when the cap is exceeded ($1.00+), but execution continues.

## How enforcement works

Budget enforcement uses Python `contextvars` to track the active budget session per asyncio task. The enforcement point is inside `LiteLLMClient.achat()` --- the single chokepoint for all LLM calls.

### The enforcement chain

1. **Workflow start:** If the workflow has `limits`, a `BudgetSession` is created and set as the active budget via `_active_budget` ContextVar.

2. **Block start:** If a block has `limits`, a child `BudgetSession` is created with the workflow session as its `parent`. The child session replaces the active budget for the duration of that block.

3. **LLM call returns:** After each `achat()` call, the session's `accrue()` method adds the cost and tokens. If the session has a parent, costs propagate up the chain automatically.

4. **Cap check:** After accrual, `check_or_raise()` walks the entire parent chain. If any session (block or workflow) has exceeded its cap with `on_exceed: "fail"`, a `BudgetKilledException` is raised.

5. **Block end:** The block's budget session is removed and the workflow session is restored.

### Parent propagation

When a block has its own limits, the `BudgetSession` is created with the workflow session as `parent`. Every `accrue()` call on the child also increments the parent's counters:

```
Block accrues $0.50, 1000 tokens
  → Block session: cost=$0.50, tokens=1000
  → Parent (workflow) session: cost=$0.50, tokens=1000 (propagated)
```

This means a workflow with `cost_cap_usd: 2.00` will kill the run even if the individual block has no limit, as long as the workflow's total cost exceeds $2.00.

### Timeout enforcement

Timeouts work differently from cost and token caps:

- **Workflow timeout:** `Workflow.run()` wraps the main execution loop in `asyncio.wait_for(timeout=max_duration_seconds)`. If the timeout fires, a `BudgetKilledException` is raised with `limit_kind="timeout"`.

- **Block timeout:** `execute_block()` wraps the individual block dispatch in `asyncio.wait_for(timeout=max_duration_seconds)`. Block timeouts are independent of the workflow timeout.

### Dispatch branch isolation

When a `dispatch` block fans out to multiple exit branches, each branch gets an **isolated child session** via `contextvars.copy_context()`. This prevents concurrent branches from sharing mutable budget state. After all branches complete, their costs are reconciled back to the parent session, and the parent's caps are checked.

```
Parent session: cost_cap=$5.00
  ├── Branch A (isolated): cost=$1.00
  ├── Branch B (isolated): cost=$2.00
  └── After reconciliation: parent cost=$3.00 → cap check passes
```

## Complete example

```yaml title="custom/workflows/budget-example.yaml"
version: "1.0"
limits:
  cost_cap_usd: 5.00
  token_cap: 200000
  max_duration_seconds: 600
  on_exceed: fail
  warn_at_pct: 0.8
workflow:
  name: budget-example
  entry: research
  transitions:
    - from: research
      to: summarize
    - from: summarize
blocks:
  research:
    type: linear
    soul_ref: researcher
    limits:
      cost_cap_usd: 3.00
      max_duration_seconds: 300
      on_exceed: fail
  summarize:
    type: linear
    soul_ref: writer
    limits:
      cost_cap_usd: 1.00
      on_exceed: warn
```

In this example:
- The workflow will hard-stop at $5.00 total or 200k tokens or 10 minutes.
- The `research` block will hard-stop at $3.00 or 5 minutes.
- The `summarize` block will warn at $1.00 but continue running.
- Both blocks' costs propagate to the workflow total.

<!-- Linear: RUN-708, RUN-717, RUN-732 — last verified against codebase 2026-04-07 -->
