---
title: Canvas Modes
description: The three WorkflowSurface modes — edit, readonly, and sim — and how they control every panel in the UI.
---

The `WorkflowSurface` component operates in one of three modes: **edit**, **readonly**, and **sim** (simulation). Each mode configures every panel in the surface — topbar, canvas, inspector, bottom panel, and status bar — through a pure-data contract defined in `workflowSurfaceContract.ts`. This means mode behavior is declarative: changing a mode flips a set of flags, and every component reads its rules from the contract.

## The three modes

### Edit mode

Edit mode is the primary authoring surface. This is the mode you see when you open a workflow from the Flows page.

| Panel | Behavior |
|-------|----------|
| **Topbar** | Workflow name is editable (click to rename). Save button appears, enabled when there are unsaved changes. Run button visible. No execution metrics. |
| **Canvas** | Nodes are draggable. Connections can be created. Nodes can be deleted (Backspace key). Cost badges show estimated values. |
| **Inspector** | Opens on double-click. Fields are editable. Tabs: Overview, Prompt, Conditions. |
| **Bottom panel** | Collapsed by default. Tabs: Logs, Runs. |
| **Status bar** | Shows block and edge counts (e.g., "3 blocks, 2 edges"). No execution metrics. |
| **Tab toggle** | Both Canvas and YAML tabs are available. |

### Readonly mode

Readonly mode is used when viewing a completed run. Nothing is editable — the surface is a read-only inspection view.

| Panel | Behavior |
|-------|----------|
| **Topbar** | Workflow name is not editable (links back to the workflow editor). Save button hidden. Fork button visible. Static execution metrics (duration, tokens, cost). |
| **Canvas** | Nodes are not draggable. No connections or deletions. Cost badges show final values. |
| **Inspector** | Opens on single-click. Fields are read-only. Tabs: Overview, Output, Eval, Error. |
| **Bottom panel** | Expanded by default. Tabs: Logs, Runs, Regressions. |
| **Status bar** | Shows progress format (e.g., "5/5 steps"). Duration and cost metrics visible. |
| **Tab toggle** | Neither Canvas nor YAML tabs are togglable — the view is fixed. |

### Sim mode

Sim mode is the surface during a live simulation run. It is read-only but shows live-updating metrics and node statuses.

| Panel | Behavior |
|-------|----------|
| **Topbar** | Workflow name is not editable. Save button hidden. Cancel button visible (to abort the run). Live execution metrics (elapsed time, running cost). |
| **Canvas** | Nodes are draggable (to rearrange while watching). Connections and deletions are allowed. Cost badges show live values. |
| **Inspector** | Opens on single-click. Fields are read-only. Tabs: Overview, Results, Conditions. |
| **Bottom panel** | Expanded by default. Tabs: Logs, Runs. |
| **Status bar** | Shows progress format. Elapsed time and cost metrics visible. |
| **Tab toggle** | Canvas tab only — YAML tab is hidden during simulation. |

:::caution
Readonly and sim modes exist in the contract and are fully specified, but **edit mode is the primary shipped mode** today. The readonly and sim mode contracts are wired into the `WorkflowSurface` component, but some panels (such as the inspector) are not yet fully connected in these modes. The `RunDetail` page implements its own readonly view separately from the `WorkflowSurface` contract.
:::

## Contract architecture

The mode contract is defined as a pure TypeScript data structure with no React dependencies. Each mode maps to a `PanelContract` object:

```typescript title="workflowSurfaceContract.ts (simplified)"
interface PanelContract {
  topbar: {
    nameEditable: boolean;
    metricsVisible: boolean;
    metricsStyle: "live" | "static" | "none";
    saveButton: "dirty-dependent" | "disabled" | "hidden";
  };
  palette: {
    visible: boolean;
    dimmed: boolean;
    searchEditable: boolean;
  };
  canvas: {
    draggable: boolean;
    connectionsAllowed: boolean;
    deletionAllowed: boolean;
    costBadgeStyle: "estimated" | "live" | "final";
  };
  inspector: {
    trigger: "double-click" | "single-click";
    fieldsEditable: boolean;
  };
  bottomPanel: {
    defaultState: "collapsed" | "expanded";
  };
  statusBar: {
    stepCountFormat: "steps-and-edges" | "progress";
    metricsVisibility: "hidden" | "elapsed-and-cost" | "duration-and-cost";
  };
}
```

Helper functions derive specific UI flags from the mode:

| Function | Returns |
|----------|---------|
| `isEditable(mode)` | Whether the mode allows any editing (fields or dragging) |
| `isDraggable(mode)` | Whether nodes can be repositioned |
| `canCreateConnections(mode)` | Whether new edges can be drawn |
| `canDeleteNodes(mode)` | Whether the delete key works |
| `getAvailableTabs(mode, panel)` | Which tabs appear in the inspector or bottom panel |
| `getActionButton(mode)` | The primary action: "Save+Run" (edit), "Cancel" (sim), "Fork" (readonly) |
| `getSaveButtonState(mode, isDirty)` | Save button state: "enabled", "disabled", or "hidden" |
| `getCostBadgeStyle(mode)` | How cost is displayed on nodes |
| `getCanvasYamlToggleVisibility(mode)` | Which tabs (Canvas, YAML) are available in the topbar |

## Mode transitions

Mode transitions happen through React state in `WorkflowSurface`:

- **Edit to sim** — when a run starts, the mode can switch to `sim` to show live execution
- **Readonly to edit** — the Fork button creates a new workflow from the run's historical YAML snapshot and navigates to edit mode via `handleForkTransition`
- **Sim to edit** — when a run completes or is cancelled, the mode returns to `edit`

The fork transition deserves special attention: it reads the YAML from the run's git commit (not the current workflow file), creates a new disabled workflow, and navigates to its edit surface. This ensures the fork reflects exactly the YAML that executed, not whatever the workflow looks like now.

## Per-mode tab maps

Each mode defines which tabs are available in the inspector and bottom panel:

| Mode | Inspector tabs | Bottom panel tabs |
|------|---------------|-------------------|
| Edit | Overview, Prompt, Conditions | Logs, Runs |
| Sim | Overview, Results, Conditions | Logs, Runs |
| Readonly | Overview, Output, Eval, Error | Logs, Runs, Regressions |

The Regressions tab only appears in readonly mode, where you can compare a completed run against previous runs to detect quality or cost regressions.

<!-- Linear: RUN-649, Visual Workflow Builder project — last verified against codebase 2026-04-07 -->
