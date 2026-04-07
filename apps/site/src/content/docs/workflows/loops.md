---
title: Loops
description: Iterate with the loop block — inner block refs, break conditions, carry context, and stateful rounds.
---

<!-- Linear: RUN-155 (Loop Refactor), RUN-703 (Loop E2E), RUN-666 (YAML DX Sugar) -->

The `loop` block runs a set of inner blocks for multiple rounds. It is the primary mechanism for iterative patterns like writer-critic refinement, progressive summarization, or retry-until-success flows.

## Basic loop

A loop block references other blocks in the same workflow by ID. Each round executes them in sequence.

```yaml title="simple 3-round loop"
blocks:
  draft:
    type: linear
    soul_ref: writer
  review:
    type: gate
    soul_ref: critic
    eval_key: draft
    pass: done
    fail: draft
  refine:
    type: loop
    inner_block_refs: [draft, review]
    max_rounds: 3
    break_on_exit: pass
  done:
    type: code
    code: |
      def main(data):
          return {"final": data.get("draft", "")}
    depends: refine

workflow:
  name: Iterative Refinement
  entry: refine
```

The loop runs `draft` then `review` each round. If `review` produces an exit handle of `"pass"`, the loop breaks early. Otherwise it continues up to 3 rounds.

## Loop block fields

| Field | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `inner_block_refs` | `List[str]` | required | min 1 item | Block IDs to execute each round, in order |
| `max_rounds` | `int` | `5` | 1--50 | Maximum number of iterations |
| `break_condition` | `ConditionDef` or `ConditionGroupDef` | none | | Condition evaluated against the last inner block's output |
| `carry_context` | `CarryContextConfig` | none | | How to pass context between rounds |
| `break_on_exit` | `str` | none | | Exit handle value that stops the loop |
| `retry_on_exit` | `str` | none | | Exit handle value that restarts the current round |

:::caution
A loop block cannot reference itself in `inner_block_refs`. Self-references raise a validation error at build time. The inner blocks must be defined in the same workflow file.
:::

## Breaking out of a loop

There are three ways to exit a loop early.

### break_on_exit

Set `break_on_exit` to an exit handle string. After each inner block executes, the engine checks the block's result. If the `exit_handle` matches, the loop stops immediately.

```yaml
refine:
  type: loop
  inner_block_refs: [draft, review]
  max_rounds: 5
  break_on_exit: pass
```

This is the most common pattern — pair it with a gate block whose `pass` exit handle triggers the break.

### break_condition

A condition evaluated against the **last** inner block's output at the end of each round. Uses the same condition engine as output conditions.

```yaml
refine:
  type: loop
  inner_block_refs: [draft, review]
  max_rounds: 5
  break_condition:
    eval_key: verdict
    operator: equals
    value: approved
```

You can also use a `ConditionGroupDef` with multiple conditions:

```yaml
break_condition:
  combinator: and
  conditions:
    - eval_key: score
      operator: gte
      value: 8
    - eval_key: verdict
      operator: equals
      value: approved
```

### retry_on_exit

Set `retry_on_exit` to an exit handle string. When a block's exit handle matches, the loop **restarts the current round** from the first inner block instead of advancing. This skips the break condition check for that round.

```yaml
refine:
  type: loop
  inner_block_refs: [draft, review]
  max_rounds: 5
  retry_on_exit: needs_revision
  break_on_exit: approved
```

## Carrying context between rounds

By default, each round starts fresh — inner blocks do not see the output of previous rounds. The `carry_context` configuration changes this by injecting prior round outputs into `shared_memory`.

```yaml
refine:
  type: loop
  inner_block_refs: [draft, review]
  max_rounds: 3
  carry_context:
    enabled: true
    mode: last
    inject_as: previous_feedback
```

### CarryContextConfig fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `true` | Enable context carrying |
| `mode` | `"last"` or `"all"` | `"last"` | `"last"`: inject only the previous round's outputs. `"all"`: inject an accumulating list of all rounds. |
| `source_blocks` | `List[str]` | none | Specific inner blocks to carry from. If omitted, all inner blocks are used. Must be a subset of `inner_block_refs`. |
| `inject_as` | `str` | `"previous_round_context"` | Key name in `shared_memory` where the carried context is stored |

### Mode: last

Injects a dict mapping source block IDs to their outputs from the previous round:

```json
{"draft": "The revised paragraph...", "review": "PASS"}
```

### Mode: all

Injects a list of all rounds' outputs, oldest first:

```json
[
  {"draft": "First attempt...", "review": "FAIL: too short"},
  {"draft": "Revised version...", "review": "PASS"}
]
```

When using `mode: all`, the engine applies budget-aware truncation to prevent context from growing unbounded. Older entries are pruned first when the carried context exceeds 3% of the model's context window.

### Injecting into task context

When `carry_context` is enabled and the workflow has a current task, the engine also injects the carried context into `task.context` as elastic data. This means inner blocks that call `fit_to_budget` can access previous round outputs without explicit prompt engineering.

## Stateful inner blocks

Setting `stateful: true` on inner blocks enables **conversation history persistence** across loop rounds. The soul remembers what it said in previous rounds, which is useful for iterative refinement where the model should build on its own prior attempts.

```yaml
blocks:
  draft:
    type: linear
    soul_ref: writer
    stateful: true    # remembers prior drafts across rounds
  review:
    type: gate
    soul_ref: critic
    eval_key: draft
    pass: done
    fail: draft
  refine:
    type: loop
    inner_block_refs: [draft, review]
    max_rounds: 3
    break_on_exit: pass
```

:::tip
Combine `stateful: true` with `carry_context` for best results. `stateful` gives the soul its own conversation memory, while `carry_context` gives it structured access to other blocks' outputs from prior rounds.
:::

## Loop metadata

After the loop completes, the engine stores metadata in `shared_memory` under the key `__loop__{block_id}`:

```json
{
  "rounds_completed": 2,
  "broke_early": true,
  "break_reason": "exit_handle 'pass' matched break_on_exit"
}
```

The `break_reason` values are:
- `"exit_handle '{handle}' matched break_on_exit"` — broke via `break_on_exit`
- `"condition met"` — broke via `break_condition`
- `"max_rounds reached"` — ran all rounds without breaking

The loop also stores the current round number during execution at `shared_memory["{block_id}_round"]`, so inner blocks can access it.

## Loop with all block types

Loop blocks work with any block type as inner blocks, including other loops, workflow blocks, gate blocks, and code blocks. The unified block execution lifecycle (`execute_block`) handles dispatch for all types inside the loop.

```yaml title="loop with code and gate inner blocks"
blocks:
  generate:
    type: code
    code: |
      def main(data):
          round_num = data.get("improve_loop_round", 1)
          return {"draft": f"Attempt {round_num}"}
  check:
    type: gate
    soul_ref: quality_checker
    eval_key: generate
    pass: done
    fail: generate
  improve_loop:
    type: loop
    inner_block_refs: [generate, check]
    max_rounds: 5
    break_on_exit: pass
```
