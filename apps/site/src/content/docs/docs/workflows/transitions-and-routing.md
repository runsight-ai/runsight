---
title: Transitions & Routing
description: How blocks connect and route in a Runsight workflow — transitions, conditional branching, exit ports, and output conditions.
---

<!-- Linear: RUN-666 (YAML DX Sugar), RUN-643 (Dispatch Unification), RUN-598 (Sub-Workflow) -->

Runsight workflows are directed graphs. Blocks connect through **transitions** that tell the engine which block to run next. This page explains every connection mechanism — from simple A-to-B transitions through conditional branching — and how the execution engine resolves the next block at runtime.

## Plain transitions

The simplest connection. A `TransitionDef` maps one block to the next.

```yaml title="workflow section"
workflow:
  name: Pipeline
  entry: research
  transitions:
    - from: research
      to: draft
    - from: draft
      to: publish
    - from: publish
      to: null    # terminal — workflow ends here
```

| Field | Type | Description |
|-------|------|-------------|
| `from` | `str` | Source block ID |
| `to` | `str` or `null` | Target block ID, or `null` for terminal |

Setting `to: null` marks the block as terminal — the workflow ends after it executes. If a block has no transition at all (not listed in `transitions` and no `depends` pointing to it), it is also terminal.

Each block can have **at most one** plain transition. Attempting to add a second raises a validation error.

## Conditional transitions

When a block needs to route to different targets based on its output, use `conditional_transitions`. Extra keys beyond `from` and `default` map decision strings to target block IDs.

```yaml title="workflow section"
workflow:
  name: Review Pipeline
  entry: classifier
  conditional_transitions:
    - from: classifier
      urgent: handle_urgent
      normal: handle_normal
      default: handle_normal
```

| Field | Type | Description |
|-------|------|-------------|
| `from` | `str` | Source block ID |
| `default` | `str` or `null` | Fallback target if no key matches |
| *(extra keys)* | `str` | Decision key mapped to target block ID |

The engine resolves which key to use via the block's **exit handle** — see the resolution order below.

A block cannot have both a plain transition and a conditional transition. The engine enforces mutual exclusivity at build time.

## Exit ports

Exit ports declare the named outputs a block can produce. Any block type can have exits, but they are most commonly used with `linear` blocks (via the `delegate` tool) and `gate` blocks (automatic `pass`/`fail`).

```yaml title="block with exits"
blocks:
  reviewer:
    type: linear
    soul_ref: review_soul
    exits:
      - id: approve
        label: Approved by reviewer
      - id: reject
        label: Rejected — needs revision
```

Each `ExitDef` has:

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Unique exit port ID |
| `label` | `str` | Human-readable label |

When a block has exits and the workflow has `conditional_transitions` for that block, the transition keys should match the exit IDs. The engine validates this at build time — a transition key that does not match any declared exit (or `"default"`) produces a validation error.

## Exit conditions

Exit conditions let you map output **content patterns** to exit handles without requiring the LLM to call a tool. The engine checks them after block execution.

```yaml title="pattern-based exit routing"
blocks:
  classifier:
    type: linear
    soul_ref: classifier_soul
    exit_conditions:
      - contains: "APPROVED"
        exit_handle: approve
      - regex: "reject|deny"
        exit_handle: reject
    exits:
      - id: approve
        label: Approved
      - id: reject
        label: Rejected
```

Each `ExitCondition` has:

| Field | Type | Description |
|-------|------|-------------|
| `contains` | `str` or `null` | Substring match against block output |
| `regex` | `str` or `null` | Regex match against block output |
| `exit_handle` | `str` | Exit handle to set when the condition matches |

Conditions are evaluated in order. The first match wins. If no condition matches, the exit handle remains `null` and the engine falls through to plain transitions.

## Output conditions

Output conditions evaluate structured data from a block's result to pick a named branch. They use the condition engine with operators like `equals`, `contains`, `gt`, and more.

```yaml title="output_conditions on a block"
blocks:
  analyze:
    type: code
    code: |
      def main(data):
          score = len(data.get("text", ""))
          return {"quality": "high" if score > 100 else "low"}
    output_conditions:
      - case_id: high_quality
        condition_group:
          conditions:
            - eval_key: quality
              operator: equals
              value: high
      - case_id: low_quality
        default: true
```

Each `CaseDef` has:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `case_id` | `str` | required | Decision string emitted when this case matches |
| `condition_group` | `ConditionGroupDef` | none | Conditions to evaluate (omit when `default: true`) |
| `default` | `bool` | `false` | Whether this is the fallback case |

A `ConditionGroupDef` contains:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `combinator` | `str` | `"and"` | `"and"` or `"or"` — how conditions combine |
| `conditions` | `List[ConditionDef]` | required | Individual conditions to evaluate |

Each `ConditionDef` has:

| Field | Type | Description |
|-------|------|-------------|
| `eval_key` | `str` | Dot-notation path into the block's result |
| `operator` | `str` | One of the supported operators (see below) |
| `value` | `Any` or `null` | Comparison value (omit for unary operators) |

### Supported operators

| Category | Operators |
|----------|-----------|
| String | `equals`, `not_equals`, `contains`, `not_contains`, `starts_with`, `ends_with`, `is_empty`, `not_empty`, `regex` |
| Numeric | `eq`, `neq`, `gt`, `lt`, `gte`, `lte` |
| Universal | `exists`, `not_exists` |

## Routes (shorthand for output conditions + transitions)

`routes` combine output conditions and conditional transitions in a single, compact block. They are **mutually exclusive** with `output_conditions` — you cannot use both on the same block.

```yaml title="routes shorthand"
blocks:
  review:
    type: code
    code: |
      def main(data):
          return {"status": "approved"}
    routes:
      - case: publish
        when:
          conditions:
            - eval_key: status
              operator: equals
              value: approved
        goto: publish
      - case: archive
        default: true
        goto: archive
```

Each `RouteDef` has:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `case` | `str` | required | Case ID for this route |
| `when` | `ConditionGroupDef` | none | Condition group (ignored on default routes) |
| `goto` | `str` | required | Target block ID |
| `default` | `bool` | `false` | Whether this is the fallback route |

Routes require **exactly one** default route. At parse time, the engine expands routes into output conditions and conditional transitions — they are pure sugar.

## How the engine resolves the next block

After a block finishes executing, the engine follows this resolution order in `_resolve_next`:

1. **Read exit handle** — check `state.results[block_id].exit_handle`. If the block set one (via the delegate tool, gate pass/fail, or exit conditions), use it.
2. **Evaluate output conditions** — if no exit handle was set and the block has `output_conditions`, evaluate them against the block's output. The winning `case_id` becomes the exit handle.
3. **Conditional transition lookup** — if the block has `conditional_transitions`, use the exit handle as a lookup key in the condition map.
4. **Default fallback** — if no key matches, fall back to the `"default"` key in the condition map. If no default exists, the engine raises a `KeyError`.
5. **Plain transition** — if no conditional transitions exist, follow the plain transition (if any). If none, the block is terminal.

## Error routing

Any block can specify an `error_route` — a target block that runs when the block fails with an exception. See [YAML DX Shortcuts](/docs/workflows/yaml-dx-shortcuts#error_route) for syntax details.

Error routing also handles **soft errors**: if a block completes but its exit handle is `"error"` (for example, a `workflow` block with `on_error: catch` that caught a child failure), the engine routes to the error target instead of the normal transition.

## depends shorthand

Instead of writing explicit transitions, use `depends` on individual blocks. The engine auto-generates transitions from the dependency to the dependent block. See [YAML DX Shortcuts](/docs/workflows/yaml-dx-shortcuts#depends) for details and examples.
