---
title: Dispatch & Delegate
description: How branching works in Runsight — the delegate tool for LLM-driven routing and the dispatch block for parallel multi-agent execution.
---

Runsight has two mechanisms for branching a workflow into multiple paths. Both use exit ports, but they work differently: one lets the LLM choose a path, the other runs all paths in parallel.

## Two branching mechanisms

| Mechanism | Block type | Who decides | Execution |
|-----------|-----------|-------------|-----------|
| **Delegate** (exit port routing) | Any block with `exits` (typically `linear`) | The LLM calls the `delegate` tool to pick one port | Sequential -- one branch runs |
| **Dispatch** | `dispatch` block | The workflow definition | Parallel -- all branches run concurrently |

## Delegate: LLM-driven routing

The delegate pattern puts the branching decision in the hands of the LLM. A block declares named exit ports, the soul uses the `delegate` tool to pick one, and the workflow engine routes to the corresponding downstream block.

### How it works

1. Define a block with `exits` -- each exit has an `id` and `label`
2. Assign a soul that has `delegate` in its `tools` list
3. At runtime, the LLM reads the available exit ports (they appear as an enum in the tool schema) and calls `delegate` with `{"port": "<exit_id>", "task": "..."}`
4. The runner captures the chosen port as the block's `exit_handle`
5. The workflow engine matches `exit_handle` against `conditional_transitions` to find the next block

### Complete example

```yaml title="custom/workflows/code-review.yaml"
version: "1.0"
tools:
  - delegate
souls:
  reviewer:
    id: reviewer
    role: Code Reviewer
    system_prompt: >
      Review the code change. If it passes quality checks, delegate to
      the "approve" port. If it needs changes, delegate to "request_changes".
      If it has critical issues, delegate to "reject".
    tools:
      - delegate
  merger:
    id: merger
    role: Merge Handler
    system_prompt: Merge the approved change.
  feedback_writer:
    id: feedback_writer
    role: Feedback Writer
    system_prompt: Write specific feedback for the requested changes.
  escalation_handler:
    id: escalation_handler
    role: Escalation Handler
    system_prompt: Escalate the critical issue to the team lead.
blocks:
  review:
    type: linear
    soul_ref: reviewer
    exits:
      - id: approve
        label: Approved
      - id: request_changes
        label: Changes Requested
      - id: reject
        label: Rejected
  merge:
    type: linear
    soul_ref: merger
  write_feedback:
    type: linear
    soul_ref: feedback_writer
  escalate:
    type: linear
    soul_ref: escalation_handler
workflow:
  name: Code Review
  entry: review
  conditional_transitions:
    - from: review
      approve: merge
      request_changes: write_feedback
      reject: escalate
```

In this workflow, the `reviewer` soul analyzes the code and makes a judgment call. The LLM sees three exit ports (`approve`, `request_changes`, `reject`) and calls the delegate tool to pick one. The workflow engine then routes to the corresponding block.

### Exit port definition

Exit ports are defined on the block, not the soul:

```yaml
exits:
  - id: approve       # The canonical exit ID (used in delegate calls and transitions)
    label: Approved    # Human-readable label (shown in UI, included in tool description)
  - id: reject
    label: Rejected
```

The `id` is what the LLM uses when calling `delegate(port="approve", task="...")`. The `label` is metadata for display.

### Wiring exits to transitions

Every exit port must have a corresponding entry in `conditional_transitions`:

```yaml
conditional_transitions:
  - from: review          # The block with exits
    approve: merge        # exit_id -> downstream block_id
    reject: escalate
```

If the LLM picks a port that has no matching transition, the workflow engine raises an error with the available options.

## Dispatch: parallel multi-agent execution

The dispatch block runs multiple branches in parallel, each with its own soul and task instruction. Unlike delegate, there is no LLM decision -- all branches execute concurrently.

### How it works

1. Define a block with `type: dispatch`
2. Each exit has `soul_ref` and `task` in addition to `id` and `label`
3. At runtime, all branches execute in parallel via `asyncio.gather`
4. Results are stored per-exit and combined

### Complete example

```yaml title="custom/workflows/research-analysis.yaml"
version: "1.0"
souls:
  web_analyst:
    id: web_analyst
    role: Web Research Analyst
    system_prompt: Research the topic from web sources and provide key findings.
  risk_reviewer:
    id: risk_reviewer
    role: Risk Analyst
    system_prompt: Identify risks, caveats, and concerns about the topic.
  synthesizer:
    id: synthesizer
    role: Report Synthesizer
    system_prompt: Combine the research findings into a coherent summary.
blocks:
  parallel_research:
    type: dispatch
    exits:
      - id: web_scan
        label: Web Research
        soul_ref: web_analyst
        task: >
          Research the topic from available sources. Provide compact
          bullet points that can be merged downstream.
      - id: risk_scan
        label: Risk Analysis
        soul_ref: risk_reviewer
        task: >
          Identify caveats, contradictions, and cost concerns
          the final report must address.
  synthesize:
    type: linear
    soul_ref: synthesizer
    depends: parallel_research
workflow:
  name: Research Analysis
  entry: parallel_research
  transitions:
    - from: parallel_research
      to: synthesize
```

### Dispatch exit definition

Dispatch exits have two additional required fields compared to regular exits:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `str` | Yes | The exit port ID. |
| `label` | `str` | Yes | Human-readable label. |
| `soul_ref` | `str` | Yes | Which soul runs this branch. |
| `task` | `str` | Yes | The task instruction for this branch. |

### How results are stored

Dispatch blocks store results in two ways:

**Per-exit results** -- each branch's output is stored at `state.results["{block_id}.{exit_id}"]`:

```
state.results["parallel_research.web_scan"]   -> BlockResult(output="...", exit_handle="web_scan")
state.results["parallel_research.risk_scan"]  -> BlockResult(output="...", exit_handle="risk_scan")
```

**Combined result** -- all branch outputs are combined as a JSON array at `state.results["{block_id}"]`:

```json
[
  {"exit_id": "web_scan", "output": "..."},
  {"exit_id": "risk_scan", "output": "..."}
]
```

Downstream blocks that use `depends` or `input_block_ids` referencing the dispatch block receive the combined result.

## When to use which

| Scenario | Use | Why |
|----------|-----|-----|
| Route to one of several handlers based on content | **Delegate** | The LLM decides which path is appropriate |
| Run multiple analyses in parallel and merge results | **Dispatch** | All paths execute; no decision needed |
| Triage incoming requests to different teams | **Delegate** | Classification is an LLM judgment |
| Gather perspectives from multiple agents on the same input | **Dispatch** | Every perspective is needed |
| Implement approval gates with pass/fail/escalate | **Delegate** | The gate outcome determines the path |

### Key differences

- **Delegate** runs one branch. The LLM picks which one. The soul needs the `delegate` tool. The block uses `conditional_transitions` for routing.
- **Dispatch** runs all branches in parallel. No tool call is involved. Each branch has its own soul and task instruction defined in the exit. Results are combined automatically.

:::note
Both mechanisms use exit ports (`exits` on the block definition), but dispatch exits require `soul_ref` and `task` fields that regular exits do not have.
:::

<!-- Linear: RUN-265 (Named Ports & Exit Strategy), RUN-283 (Fan-Out v2) — last verified against codebase 2026-04-07 -->
