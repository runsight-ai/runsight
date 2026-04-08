---
title: Canvas Overview
description: How the Runsight visual canvas works — ReactFlow rendering, sidecar coordinate storage, and the component architecture.
---

The Runsight visual canvas displays workflows as nodes and edges on an infinite-pan canvas, powered by [XY Flow](https://xyflow.com/) (the library behind ReactFlow). Workflow **logic** lives in YAML files, while **visual layout** (node positions, viewport, selection) is stored in a separate JSON sidecar file.

:::caution
The visual canvas is under active development. The YAML editor is the primary authoring surface today. See [YAML Editor](/docs/visual-builder/yaml-editor).
:::

## Storage architecture

A Runsight workflow has two persistent representations:

| Layer | Format | Storage | Contains |
|-------|--------|---------|----------|
| Logic | YAML | `custom/workflows/{id}.yaml` | Blocks, transitions, config, version |
| Layout | JSON | Canvas sidecar (JSON alongside YAML) | Node positions, edge routing, viewport, selected node, canvas mode |

The YAML file is the source of truth for execution. The canvas sidecar stores visual-only data that the engine never reads. This separation means you can edit YAML in any text editor without losing your canvas layout, and canvas rearrangements never touch the workflow logic.

:::note
The sidecar JSON is written atomically alongside the YAML file. If the sidecar write fails, the YAML save still succeeds — layout data is treated as non-critical.
:::

## YAML-to-graph conversion

Two modules handle the conversion between YAML text and the ReactFlow graph.

### yamlParser — YAML to graph

`yamlParser.parseWorkflowYamlToGraph()` takes raw YAML text and an optional persisted canvas state, then returns ReactFlow nodes and edges:

1. Parses the YAML string into a JavaScript object
2. Iterates over the `blocks` dictionary, building a `StepNodeData` object for each block
3. Looks up each node's position from the persisted canvas state; if not found, assigns a grid position (280px horizontal spacing, 160px vertical spacing, 4 columns)
4. Builds edges from `workflow.transitions` (plain edges) and `workflow.conditional_transitions` (edges with source handles keyed to decision names)
5. Returns `{ nodes, edges, viewport, error }` — errors are returned as data, never thrown

All block fields are converted from `snake_case` (YAML) to `camelCase` (JavaScript) recursively for nested objects. The conversion is generic — there is no hardcoded list of fields per block type.

### yamlCompiler — graph to YAML

`yamlCompiler.compileGraphToWorkflowYaml()` takes ReactFlow nodes, edges, and metadata, then produces three outputs:

1. **YAML string** — clean workflow YAML with `version`, `config` (if present), `blocks`, and `workflow` sections. Runtime-only fields (`stepId`, `name`, `status`, `cost`, `executionCost`) are stripped. All `camelCase` keys are converted back to `snake_case`.
2. **Canvas state** — minimal persisted state containing only `{ id, position }` per node, plus edges, viewport, selected node ID, and canvas mode.
3. **Workflow document** — the compiled JavaScript object before YAML serialization.

Nodes with `outputConditions` produce `conditional_transitions` in the compiled YAML. The source handle on each edge maps to the decision key; a `null` source handle maps to the `default` key.

## Nodes and edges

### Node types

The canvas uses a single node component type (`canvasNode`) for all blocks. Each node displays:

- An icon derived from the block type
- The block name (truncated to fit)
- A cost badge (estimated, live, or final depending on the surface mode)
- A status indicator (idle, pending, running, completed, failed)

The `StepNodeData` interface carries all block fields from the YAML schema. The `stepType` field determines which icon and behavior apply. Supported step types include `linear`, `dispatch`, `gate`, `code`, `loop`, and `workflow`, among others.

### Edge types

Edges connect source blocks to target blocks. There are two categories:

- **Plain transitions** — from blocks without `outputConditions`. These map to `workflow.transitions` entries (`from` / `to`).
- **Conditional transitions** — from blocks with `outputConditions`. Each edge carries a `sourceHandle` that maps to a decision key. These map to `workflow.conditional_transitions` entries.

Edges render as straight lines with arrow markers by default, using the `--border-default` CSS variable for color.

## Canvas store

The canvas state is managed by a Zustand store (`useCanvasStore`) that holds:

| Field | Type | Description |
|-------|------|-------------|
| `nodes` | `Node[]` | ReactFlow node array |
| `edges` | `Edge[]` | ReactFlow edge array |
| `viewport` | `Viewport` | Pan/zoom state (`x`, `y`, `zoom`) |
| `isDirty` | `boolean` | Whether unsaved changes exist |
| `selectedNodeId` | `string \| null` | Currently selected node |
| `canvasMode` | `"dag" \| "state-machine"` | Layout mode |
| `yamlContent` | `string` | Current YAML text |
| `blockCount` | `number` | Number of blocks (parsed from YAML) |
| `edgeCount` | `number` | Number of transitions |
| `activeRunId` | `string \| null` | ID of the currently executing run |
| `runCost` | `number` | Accumulated cost from the active run |

The store provides actions for node/edge changes, selection, status updates during execution, hydration from persisted state, and serialization back to persisted state.

## Canvas controls

The canvas includes standard ReactFlow controls:

- **Pan and zoom** — scroll to zoom, drag to pan the background
- **Fit view** — automatically enabled on load with 0.3 padding
- **Controls panel** — zoom in, zoom out, fit view buttons
- **MiniMap** — shows a bird's-eye view with nodes colored by type
- **Dot grid background** — 28px gap, subtle dots for spatial orientation

:::tip
The YAML editor tab is the primary authoring surface today. See [YAML Editor](/docs/visual-builder/yaml-editor) for details.
:::

## Component architecture

The canvas is composed from these main components:

- **`WorkflowSurface`** — the top-level orchestrator. Manages mode (edit/readonly/sim), loads workflow data, coordinates the topbar, editor, bottom panel, and status bar. See [Canvas Modes](/docs/visual-builder/canvas-modes).
- **`WorkflowCanvas`** — the ReactFlow wrapper. Renders nodes and edges, delegates to the canvas store.
- **`YamlEditor`** — Monaco-based YAML editing. See [YAML Editor](/docs/visual-builder/yaml-editor).
- **`CanvasTopbar`** — workflow name (editable in edit mode), canvas/YAML tab toggle, save button, run button, and execution metrics.
- **`CanvasBottomPanel`** — collapsible panel with Logs, Runs, and Regressions tabs. Connects to SSE for real-time log streaming during execution.
- **`CanvasStatusBar`** — footer showing block/edge counts and the active tab indicator.

<!-- Linear: RUN-649, Visual Workflow Builder project — last verified against codebase 2026-04-07 -->
