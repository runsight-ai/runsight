---
title: Unified Entity Identity
description: Reference for entity ids, YAML identity fields, filename rules, and workflow references.
---

## Identity Model

Runsight uses one identity model for persisted YAML-backed entities.

| Concept | Value | Notes |
|---|---|---|
| Entity kinds | `soul`, `workflow`, `tool`, `provider`, `assertion` | There is no `step` kind. |
| Entity reference | `{kind}:{id}` | Used in identity-related messages, such as `tool:http`. |
| Embedded id | `id` | Canonical machine identity. |
| Embedded kind | `kind` | Must match the entity family. |
| Display name | `name` or `workflow.name` | Human label, not identity. |
| Filename stem | `{id}` | Must match the embedded id exactly. |

```python title="entity ref"
from runsight_core.identity import EntityKind, EntityRef

ref = EntityRef(kind=EntityKind.WORKFLOW, id="research-review")
str(ref)  # "workflow:research-review"
```

## ID Rules

Every entity id must satisfy the shared entity id validator.

| Rule | Constraint |
|---|---|
| Length | 3 to 100 characters |
| Start | Lowercase letter |
| End | Lowercase letter or digit |
| Middle characters | Lowercase letters, digits, `_`, or `-` |
| Reserved ids | `pause`, `resume`, `kill`, `cancel`, `status`, `http`, `file_io`, `delegate` |

Valid examples:

- `researcher`
- `research-review`
- `slack_webhook`
- `openai`

Invalid examples:

- `AI-review`
- `99-review`
- `ab`
- `tool/evil`
- `http`

## YAML Examples

### Workflow

```yaml title="custom/workflows/summarizer.yaml"
version: "1.0"
id: summarizer
kind: workflow

interface:
  inputs:
    - name: topic
      target: shared_memory.topic
      type: string
      required: true
  outputs:
    - name: summary
      source: results.summarize
      type: string

souls:
  writer:
    id: writer
    kind: soul
    name: Writer
    role: Summarizer
    system_prompt: "Write a concise summary of shared_memory.topic."

blocks:
  summarize:
    type: linear
    soul_ref: writer

workflow:
  name: Summarizer
  entry: summarize
```

### Soul

```yaml title="custom/souls/researcher.yaml"
id: researcher
kind: soul
name: Senior Researcher
role: Researcher
system_prompt: "Find the relevant facts and cite the evidence."
provider: openai
model_name: gpt-4o
```

### Tool

```yaml title="custom/tools/slack_payload_builder.yaml"
version: "1.0"
id: slack_payload_builder
kind: tool
type: custom
executor: python
name: Slack Payload Builder
description: Build a JSON payload string for Slack.
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

### Assertion

```yaml title="custom/assertions/budget_guard.yaml"
version: "1.0"
id: budget_guard
kind: assertion
name: Budget Guard
description: Keeps cost under budget.
returns: bool
source: budget_guard.py
```

```python title="custom/assertions/budget_guard.py"
def get_assert(output, context):
    return True
```

### Provider

```yaml title="custom/providers/openai.yaml"
id: openai
kind: provider
name: OpenAI
type: openai
is_active: true
```

## Filename Convention

Use the embedded id as the filename stem.

| Kind | Directory | Example |
|---|---|---|
| `workflow` | `custom/workflows/` | `custom/workflows/research-review.yaml` |
| `soul` | `custom/souls/` | `custom/souls/researcher.yaml` |
| `tool` | `custom/tools/` | `custom/tools/slack_webhook.yaml` |
| `provider` | `custom/providers/` | `custom/providers/openai.yaml` |
| `assertion` | `custom/assertions/` | `custom/assertions/budget_guard.yaml` |

The embedded `id` must match the filename stem exactly. `custom/workflows/summarizer.yaml` must contain `id: summarizer`.

## Scanner Behavior

Scanners extract identity from YAML content.

| Scanner | Required identity | Rejection behavior |
|---|---|---|
| Workflow scanner | `id`, `kind: workflow` | Missing fields, invalid ids, duplicate ids, and id/stem mismatches fail. |
| Soul scanner | `id`, `kind: soul`, `name` | Missing fields, invalid ids, duplicate ids, and id/stem mismatches fail. |
| Tool scanner | `id`, `kind: tool` | Reserved builtin ids, invalid ids, and id/stem mismatches fail. |
| Assertion scanner | `id`, `kind: assertion` | Builtin assertion id collisions, invalid ids, and id/stem mismatches fail. |

Use `ScanIndex.ids()` and `without_ids()` when working with discovered entities. Stem-based helpers are not part of the final identity API.

## Repository Behavior

Repositories persist by embedded id.

| Repository | Behavior |
|---|---|
| Workflow repository | Creates and updates `custom/workflows/{id}.yaml`. Duplicate create fails before write. Update cannot change `id`. |
| Soul repository | Uses `custom/souls/{id}.yaml` through the shared YAML repository behavior. |
| Provider repository | Creates and updates `custom/providers/{id}.yaml`, with provider ids validated by the shared rules. |

Repositories reject malformed or mismatched identity. They do not repair a missing id from the filename, and they do not derive ids from display names.

## Workflow References

`workflow_ref` resolves by embedded workflow id only.

Accepted:

```yaml
blocks:
  summarize:
    type: workflow
    workflow_ref: summarizer
```

Rejected:

- `custom/workflows/summarizer.yaml`
- `summarizer.yaml`
- `Summarizer`
- relative paths
- workflow display names

The resolver does not apply path, stem, relative-path, or display-name aliases.

## Runs, Simulations, and Forks

New run records store the embedded workflow id in `workflow_id`. Historical run records that contain old ids are not backfilled.

A simulation branch keeps the same embedded workflow id. The simulation is identified by the branch plus the workflow id, not by mutating the workflow YAML.

A fork is different from a simulation. Forking creates a disabled draft workflow with a new embedded workflow id. Nested `workflow_ref` values remain unchanged.

## GUI Create Contract

Workflow creation in the GUI submits YAML that already contains `id` and `kind: workflow`.

```yaml title="workflow draft"
version: "1.0"
id: research-review
kind: workflow
workflow:
  name: Research Review
  entry: start
blocks:
  start:
    type: code
    code: |
      def main(data):
          return {"ok": True}
```

The create UI exposes an editable workflow id. The default id is derived from the workflow name, but the user can change it before creation. Backend validation remains the final authority.

Provider creation also carries embedded identity in the request body:

```json title="POST /api/settings/providers"
{
  "id": "openai",
  "kind": "provider",
  "name": "OpenAI",
  "api_key_env": "OPENAI_API_KEY"
}
```

## Adding a YAML-Backed Entity Kind

Use this checklist when adding a future YAML-backed entity kind:

1. Add the kind to `EntityKind`.
2. Require a literal `kind` field in the schema.
3. Require `id` and validate it with the shared id rules.
4. Enforce `id == filename stem`.
5. Extract ids from YAML in the scanner.
6. Reject duplicate embedded ids.
7. Resolve references by embedded id only.
8. Add repository create/update validation.
9. Update GUI create flows if users can create the entity from the UI.
10. Add targeted tests and docs.

## Scope Exclusions

Unified entity identity does not define:

- `EntityKind.STEP`
- display-name, path, or filename aliases for `workflow_ref`
- a separate simulation entity id
- historical run backfills
- stem-based APIs such as `ScanIndex.stems()` or `without_stems()`

Runtime step wrappers still exist in execution code, but they are Python/plugin execution concepts, not persisted YAML entity identity.

<!-- Linear: RUN-773, RUN-835, RUN-846 — last verified against codebase 2026-04-13 -->
