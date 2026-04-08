---
title: YAML Schema Reference
description: Complete annotated reference for all Runsight YAML file types — workflow files, soul files, and custom tool files.
---

<!-- RUN-110, RUN-490 -->

Runsight uses three YAML file types. This page is the exhaustive field reference for all three. For a guided walkthrough of workflow files, see [YAML Schema](/docs/workflows/yaml-schema).

## Workflow files

Workflow files live in `custom/workflows/` and define the full execution graph. The root model is `RunsightWorkflowFile`.

### Top-level fields

| Field | Type | Default | Required | Description |
|-------|------|---------|----------|-------------|
| `version` | `str` | `"1.0"` | no | Schema version |
| `enabled` | `bool` | `false` | no | Whether the workflow is active |
| `config` | `Dict[str, Any]` | `{}` | no | Arbitrary workflow configuration |
| `interface` | `WorkflowInterfaceDef` | none | no | Public input/output contract for callable sub-workflows |
| `tools` | `List[str]` | `[]` | no | Tool IDs available to souls in this workflow. Duplicates are rejected. |
| `souls` | `Dict[str, SoulDef]` | `{}` | no | Inline soul definitions. The dict key must match the soul's `id` field. |
| `blocks` | `Dict[str, BlockDef]` | `{}` | no | Block definitions keyed by block ID. Uses a discriminated union on `type`. |
| `workflow` | `WorkflowDef` | -- | **yes** | Graph metadata (name, entry point, transitions) |
| `limits` | `WorkflowLimitsDef` | none | no | Workflow-level budget constraints |
| `eval` | `EvalSectionDef` | none | no | Embedded test cases for offline evaluation |

### WorkflowDef

| Field | Type | Default | Required | Description |
|-------|------|---------|----------|-------------|
| `name` | `str` | -- | **yes** | Workflow name |
| `entry` | `str` | -- | **yes** | Block ID to start execution |
| `transitions` | `List[TransitionDef]` | `[]` | no | Simple A to B transitions |
| `conditional_transitions` | `List[ConditionalTransitionDef]` | `[]` | no | Multi-path transitions based on output |

### TransitionDef

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `from` | `str` | **yes** | Source block ID |
| `to` | `str` or `null` | no | Target block ID, or `null` for terminal |

### ConditionalTransitionDef

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `from` | `str` | **yes** | Source block ID |
| `default` | `str` or `null` | no | Fallback target if no key matches |
| *(extra keys)* | `str` | no | Decision key mapped to target block ID |

### WorkflowInterfaceDef

Public callable contract for sub-workflows.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `inputs` | `List[WorkflowInterfaceInputDef]` | `[]` | Input parameters. Names must be unique. |
| `outputs` | `List[WorkflowInterfaceOutputDef]` | `[]` | Output parameters. Names must be unique. |

#### WorkflowInterfaceInputDef

| Field | Type | Default | Required | Description |
|-------|------|---------|----------|-------------|
| `name` | `str` | -- | **yes** | Input parameter name (must be unique) |
| `target` | `str` | -- | **yes** | Dot-notation path to child state key |
| `type` | `str` | none | no | Type hint |
| `required` | `bool` | `true` | no | Whether input must be provided |
| `default` | `Any` | none | no | Default value if not provided |
| `description` | `str` | none | no | Human-readable description |

#### WorkflowInterfaceOutputDef

| Field | Type | Default | Required | Description |
|-------|------|---------|----------|-------------|
| `name` | `str` | -- | **yes** | Output parameter name (must be unique) |
| `source` | `str` | -- | **yes** | Dot-notation path to child result |
| `type` | `str` | none | no | Type hint |
| `description` | `str` | none | no | Human-readable description |

### WorkflowLimitsDef

| Field | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `max_duration_seconds` | `int` | none | 1--86400 | Maximum wall-clock time |
| `cost_cap_usd` | `float` | none | >= 0.0 | Maximum cost in USD |
| `token_cap` | `int` | none | >= 1 | Maximum total tokens |
| `on_exceed` | `str` | `"fail"` | `"warn"` or `"fail"` | Action when limit is exceeded |
| `warn_at_pct` | `float` | `0.8` | 0.0--1.0 | Threshold percentage to trigger a warning |

### BlockLimitsDef

Same as `WorkflowLimitsDef` but without `warn_at_pct`. Applied per block via the `limits` field.

| Field | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `max_duration_seconds` | `int` | none | 1--86400 | Maximum wall-clock time |
| `cost_cap_usd` | `float` | none | >= 0.0 | Maximum cost in USD |
| `token_cap` | `int` | none | >= 1 | Maximum total tokens |
| `on_exceed` | `str` | `"fail"` | `"warn"` or `"fail"` | Action when limit is exceeded |

### Block types

The `blocks` dict uses a discriminated union on the `type` field. Each block type extends `BaseBlockDef` and adds its own fields. The following sections document block types with non-trivial additional fields.

#### WorkflowBlockDef (`type: "workflow"`)

Calls a child workflow as a sub-workflow (hierarchical state machine). The parent block binds values into the child's declared `interface` and reads results back out after the child completes.

| Field | Type | Default | Required | Description |
|-------|------|---------|----------|-------------|
| `type` | `"workflow"` | -- | **yes** | Discriminator |
| `workflow_ref` | `str` | -- | **yes** | Slug or path of the child workflow to call |
| `inputs` | `Dict[str, str]` | none | no | Maps child interface input names to parent dotted paths (e.g. `topic: shared_memory.topic`) |
| `outputs` | `Dict[str, str]` | none | no | Maps parent dotted paths to child interface output names (e.g. `shared_memory.summary: summary`) |
| `max_depth` | `int` | none (runtime default 10) | no | Maximum HSM recursion depth |
| `on_error` | `"raise"` or `"catch"` | `"raise"` | no | `"catch"` swallows child failure and returns an error exit handle instead of propagating |

All inherited `BaseBlockDef` fields (`stateful`, `routes`, `depends`, `error_route`, `retry_config`, `exits`, `exit_conditions`, `timeout_seconds`, `limits`, etc.) are also available.

**Validation rules:**
- `inputs` keys must be plain interface names (no dots). They reference the child workflow's `interface.inputs[].name`.
- `outputs` values must be plain interface names (no dots). They reference the child workflow's `interface.outputs[].name`.

#### Sub-workflow example

The parent workflow defines a `workflow` block that calls a child. The child declares its callable contract via the top-level `interface` section.

**Parent workflow** -- calls the child and wires data in and out:

```yaml title="custom/workflows/research_pipeline.yaml"
version: "1.0"
enabled: true

blocks:
  run_analysis:
    type: workflow
    workflow_ref: analysis_subworkflow
    inputs:
      topic: shared_memory.topic
      depth: shared_memory.analysis_depth
    outputs:
      shared_memory.summary: summary
      shared_memory.citations: sources
    max_depth: 5
    on_error: catch
    timeout_seconds: 600

workflow:
  name: Research Pipeline
  entry: run_analysis
  transitions:
    - from: run_analysis
      to: null
```

**Child workflow** -- declares the interface contract the parent binds to:

```yaml title="custom/workflows/analysis_subworkflow.yaml"
version: "1.0"
enabled: true

interface:
  inputs:
    - name: topic
      target: shared_memory.topic
      type: string
      required: true
      description: The research topic to analyze
    - name: depth
      target: shared_memory.depth
      type: integer
      required: false
      default: 3
      description: How many layers deep to research
  outputs:
    - name: summary
      source: shared_memory.final_summary
      type: string
      description: Completed analysis summary
    - name: sources
      source: shared_memory.collected_sources
      type: list
      description: List of cited sources

souls:
  analyst:
    id: analyst
    role: Research Analyst
    system_prompt: "Analyze the topic in shared_memory.topic."

blocks:
  analyze:
    type: soul
    soul_ref: analyst
    task: "Research the topic and write a summary."

workflow:
  name: Analysis Sub-Workflow
  entry: analyze
  transitions:
    - from: analyze
      to: null
```

In the parent, `inputs` keys (`topic`, `depth`) match the child's `interface.inputs[].name` values. The parent values (`shared_memory.topic`, `shared_memory.analysis_depth`) are dotted paths into the parent's own state.

In the parent, `outputs` values (`summary`, `sources`) match the child's `interface.outputs[].name` values. The parent keys (`shared_memory.summary`, `shared_memory.citations`) are dotted paths where results are written in the parent's state.

### EvalSectionDef

| Field | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `threshold` | `float` | none | 0.0--1.0 | Pass rate threshold for the suite |
| `cases` | `List[EvalCaseDef]` | -- | min 1 item, unique IDs | Test case definitions |

#### EvalCaseDef

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | `str` | -- | Unique test case ID (strict string) |
| `description` | `str` | none | Human-readable description |
| `inputs` | `Dict[str, Any]` | none | Input data for the workflow |
| `fixtures` | `Dict[str, str]` | none | Block ID to mock output (skips LLM calls) |
| `expected` | `Dict[str, List[Dict[str, Any]]]` | none | Block ID to list of assertion configs |

### Supporting models

#### ConditionDef

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `eval_key` | `str` | -- | Dot-notation path into block's own result |
| `operator` | `str` | -- | Comparison operator |
| `value` | `Any` | none | Comparison value (none for unary operators like `is_empty`, `exists`) |

#### ConditionGroupDef

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `combinator` | `str` | `"and"` | `"and"` or `"or"` |
| `conditions` | `List[ConditionDef]` | -- | List of conditions to combine |

#### CaseDef

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `case_id` | `str` | -- | Unique case identifier |
| `condition_group` | `ConditionGroupDef` | none | Conditions for this case (none when `default: true`) |
| `default` | `bool` | `false` | Whether this is the default/fallback case |

#### RouteDef

Shorthand route definition that compiles into output conditions and transitions.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `case` | `str` | -- | Case identifier (YAML alias for `case_id`) |
| `when` | `ConditionGroupDef` | none | Conditions for this route |
| `goto` | `str` | -- | Target block ID |
| `default` | `bool` | `false` | Whether this is the default route |

Exactly one route must have `default: true`. Route `case` values must be unique.

#### InputRef

| Field | Type | Description |
|-------|------|-------------|
| `from` | `str` | Dot-notation reference to upstream block output (e.g. `"step_id.output_field"`) |

#### ExitDef

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Unique exit port ID |
| `label` | `str` | Human-readable label |

#### DispatchExitDef

Extends `ExitDef` with per-exit soul and task instruction.

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Unique exit port ID |
| `label` | `str` | Human-readable label |
| `soul_ref` | `str` | Soul ID for this branch |
| `task` | `str` | Task instruction for this branch's soul |

#### ExitCondition

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `contains` | `str` | none | Substring match against output |
| `regex` | `str` | none | Regex pattern match against output |
| `exit_handle` | `str` | -- | Exit handle value to set on match |

#### RetryConfig

| Field | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `max_attempts` | `int` | `3` | 1--20 | Maximum retry attempts |
| `backoff` | `str` | `"fixed"` | `"fixed"` or `"exponential"` | Backoff strategy |
| `backoff_base_seconds` | `float` | `1.0` | 0.1--60.0 | Base delay between retries |
| `non_retryable_errors` | `List[str]` | none | -- | Error types that should not be retried |

---

## Soul files

Soul files live in `custom/souls/` as standalone YAML files (one soul per file). The filename stem becomes the soul key. Soul files are flat -- no wrapper object, just the fields directly.

### SoulDef fields

| Field | Type | Default | Required | Description |
|-------|------|---------|----------|-------------|
| `id` | `str` | -- | **yes** | Unique identifier for the soul |
| `role` | `str` | -- | **yes** | The role of the agent (e.g. `"Senior Researcher"`) |
| `system_prompt` | `str` | -- | **yes** | System instructions defining the agent's behavior |
| `tools` | `List[str]` | none | no | Tool name references available to this soul |
| `required_tool_calls` | `List[str]` | none | no | Tool function names that must be called before completion |
| `max_tool_iterations` | `int` | `5` | no | Maximum tool-use iterations per execution |
| `model_name` | `str` | none | no | Model override (uses runner default if not set) |
| `provider` | `str` | none | no | Provider override for the selected model |
| `temperature` | `float` | none | no | Sampling temperature override |
| `max_tokens` | `int` | none | no | Output token limit override |
| `avatar_color` | `str` | none | no | UI color hint for displaying the soul |
| `modified_at` | `str` | none | no | Timestamp of last modification |

### Example soul file

```yaml title="custom/souls/researcher.yaml"
id: researcher_1
role: Senior Researcher
system_prompt: >
  You are a senior researcher. Analyze the given topic thoroughly
  and produce a structured research report with citations.
tools: null
max_tool_iterations: 5
model_name: gpt-4.1-mini
provider: openai
temperature: 0.7
max_tokens: null
avatar_color: primary
modified_at: null
```

Souls can also be defined inline in a workflow file under the `souls:` section. When inline, the dict key must match the soul's `id` field:

```yaml title="workflow with inline soul"
souls:
  my_analyst:
    id: my_analyst
    role: Analyst
    system_prompt: "Analyze the data."
```

If a soul file and an inline soul share the same key, the inline definition takes precedence and a warning is logged.

---

## Custom tool files

Custom tool files live in `custom/tools/` as standalone YAML files (one tool per file). The filename stem becomes the tool ID. Reserved builtin tool IDs (`http`, `file_io`, `delegate`) cannot be used.

### Tool file fields

| Field | Type | Default | Required | Description |
|-------|------|---------|----------|-------------|
| `version` | `str` | -- | **yes** | Schema version (e.g. `"1.0"`) |
| `type` | `str` | -- | **yes** | Must be `"custom"` |
| `executor` | `str` | -- | **yes** | `"python"` or `"request"` |
| `name` | `str` | -- | **yes** | Human-readable tool name |
| `description` | `str` | -- | **yes** | Description of what the tool does |
| `parameters` | `Dict` | -- | **yes** | JSON Schema object describing the tool's input parameters |
| `code` | `str` | none | conditional | Python source code with `def main(args)`. Required for `executor: python` unless `code_file` is set. |
| `code_file` | `str` | none | conditional | Path to external Python file (relative to tool YAML). Mutually exclusive with `code`. |
| `request` | `Dict` | none | conditional | HTTP request configuration. Required for `executor: request`. |
| `timeout_seconds` | `int` | none | no | Request timeout in seconds. Only valid for `executor: request`. Must be a positive integer. |

### Request configuration (executor: request)

| Field | Type | Default | Required | Description |
|-------|------|---------|----------|-------------|
| `method` | `str` | `"GET"` | **yes** | HTTP method |
| `url` | `str` | -- | **yes** | Request URL. Supports `${ENV_VAR}` substitution. |
| `headers` | `Dict[str, str]` | `{}` | no | Request headers |
| `body_template` | `str` | none | no | Request body template with `{{ param }}` substitution |
| `response_path` | `str` | none | no | JSONPath to extract from response |

### Example: Python executor

```yaml title="custom/tools/slack_payload_builder.yaml"
version: "1.0"
type: custom
executor: python
name: Slack Payload Builder
description: Build a JSON payload string for the Slack incoming webhook.
parameters:
  type: object
  properties:
    text:
      type: string
      description: Message text to encode for Slack.
  required:
    - text
code: |
  import json

  def main(args):
      text = str(args.get("text", ""))
      return {"payload_json": json.dumps({"text": text})}
```

### Example: Request executor

```yaml title="custom/tools/slack_webhook.yaml"
version: "1.0"
type: custom
executor: request
name: Slack Webhook
description: Send a message to the configured Slack incoming webhook.
parameters:
  type: object
  properties:
    payload_json:
      type: string
      description: Complete JSON payload to send to Slack.
  required:
    - payload_json
request:
  method: POST
  url: "${SLACK_WEBHOOK_URL}"
  headers:
    Content-type: application/json
  body_template: "{{ payload_json }}"
timeout_seconds: 10
```

---

## JSON schema for editors

A JSON schema is auto-generated from the Pydantic models for Monaco editor autocomplete:

```bash
python packages/core/scripts/generate_schema.py          # generate to disk
python packages/core/scripts/generate_schema.py --check   # CI mode: exit 1 if out of sync
```

The generated schema lives at `packages/core/runsight-workflow-schema.json`.
