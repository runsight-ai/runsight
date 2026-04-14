---
title: "ADR: Unified Entity Identity"
description: Why Runsight uses embedded kind and id fields for YAML-backed entities.
---

## Status

Accepted.

YAML-backed Runsight entities use embedded `kind` and `id` fields as their source of truth. Filenames still matter, but only as a storage invariant: the filename stem must equal the embedded id.

## Context

Runsight stores workflows, souls, tools, providers, and assertions as YAML-backed assets. Before unified identity, different paths could treat a filename stem, display name, file path, or embedded field as the entity identity.

That made reference resolution ambiguous. A `workflow_ref` could look like a file path in one path and a workflow name in another. Create flows could produce files whose storage name did not match the identity used by scanners or execution. Error messages also used bare ids, which made it unclear whether a message referred to a soul, workflow, tool, provider, or assertion.

The identity model now gives every YAML-backed entity the same shape and the same validation boundary.

## Decision

Runsight identifies YAML-backed entities by `kind + id`.

| Decision | Result |
|---|---|
| Entity kinds | `soul`, `workflow`, `tool`, `provider`, `assertion` |
| Entity reference format | `{kind}:{id}`, such as `soul:researcher` |
| YAML identity | `kind` and `id` are required in every YAML-backed entity |
| Filename convention | Store YAML at `custom/<kind plural>/<id>.yaml` |
| Filename validation | Reject YAML when embedded `id` does not equal the filename stem |
| Workflow references | Resolve `workflow_ref` by embedded workflow id only |
| Display names | Human labels only; never canonical identity |

There is no defaulted `kind` in the final contract. YAML must carry the field explicitly.

## Scope

This decision applies to YAML-backed entities:

- souls in `custom/souls/`
- workflows in `custom/workflows/`
- tools in `custom/tools/`
- providers in `custom/providers/`
- assertions in `custom/assertions/`

It also applies to scanners, repositories, workflow reference resolution, identity-related messages, GUI create payloads, forked workflows, and simulation/run contracts.

This decision does not add a `step` entity kind. Runtime step discovery is Python plugin discovery and is outside this YAML identity model.

## Consequences

The runtime has one lookup story. It no longer guesses whether a value is a path, a filename stem, a display name, or an embedded id.

The trade-off is stricter validation:

- ids must follow the shared entity id rules
- reserved ids are rejected
- id/filename mismatches fail instead of being repaired
- duplicate embedded ids fail instead of silently overwriting
- old path/name aliases for `workflow_ref` are not accepted

Compatibility shims such as `ScanIndex.stems()` and `without_stems()` are not part of the final state.

## Migration Contracts

New YAML must use the embedded id contract. Existing production YAML was migrated to the same shape during the RUN-773 work.

| Contract | Required behavior |
|---|---|
| Entity id | Embedded `id` is the canonical id |
| Entity kind | Embedded `kind` identifies the entity family |
| Filename | Filename stem equals embedded id |
| Workflow ref | `workflow_ref` is the embedded workflow id |
| Run records | New records store the embedded workflow id |
| Historical runs | Old run records are not backfilled |
| Simulation branches | Simulation YAML must not mutate workflow id |
| Forked workflows | Forks get a new embedded workflow id |
| GUI create | Create flows submit YAML with `kind: workflow` and an editable id |

Simulation identity is the pair `branch + workflow_id`; there is no separate simulation entity id.

## Future YAML-Backed Kinds

Adding a future YAML-backed entity kind requires the same model:

1. Add an `EntityKind` value.
2. Require a literal `kind` field in the schema.
3. Require and validate `id`.
4. Enforce `id == filename stem`.
5. Index and resolve by embedded id.
6. Reject duplicates.
7. Add targeted tests and docs.

Do not add path, stem, or display-name aliases as compatibility fallbacks.

<!-- Linear: RUN-773, RUN-835, RUN-846 — last verified against codebase 2026-04-13 -->
