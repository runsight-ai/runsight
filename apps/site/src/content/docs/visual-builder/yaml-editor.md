---
title: YAML Editor
description: How to use the Monaco-based YAML editor for workflow authoring — syntax highlighting, live validation, and canvas sync.
---

The YAML editor is the primary authoring surface for Runsight workflows. It embeds the Monaco editor (the same engine behind VS Code) with YAML syntax highlighting, a custom color theme, and live validation that flags syntax errors as you type.

## Opening the editor

When you open a workflow from the Flows page, the editor loads in the YAML tab by default. The Canvas tab shows a placeholder — the drag-and-drop builder is under active development, so the YAML editor is where authoring happens today.

Toggle between Canvas and YAML using the tab switcher in the topbar. In edit mode, both tabs are available. In sim mode, only the Canvas tab is shown. In readonly mode, neither tab is togglable.

## Writing workflow YAML

Type your workflow definition directly in the editor. A minimal workflow looks like this:

```yaml title="custom/workflows/my-workflow.yaml"
version: "1.0"
blocks:
  summarize:
    type: linear
    soul_ref: analyst
workflow:
  name: My Workflow
  entry: summarize
  transitions: []
```

The editor provides standard code editing features:

- **Syntax highlighting** — keys, strings, numbers, and comments are colored using the Runsight YAML theme, which reads from CSS variables (`--syntax-key`, `--syntax-string`, `--syntax-value`, `--syntax-comment`, `--syntax-punct`) to match your current theme
- **Line numbers** — always visible
- **Keyboard shortcuts** — Cmd+S / Ctrl+S triggers the save action (opens the commit dialog)
- **Undo/redo** — standard Monaco undo history

## Live validation

The editor validates your YAML on every keystroke with a 500ms debounce. When the YAML contains a syntax error, the editor:

1. Parses the YAML using the `yaml` library
2. Extracts the error position (line and column)
3. Sets a Monaco error marker at that position — a red squiggly underline appears on the offending line
4. Reports the validation state (`isValid`, `errorCount`, error details)

When the error is fixed, the marker clears immediately.

:::note
Live validation currently checks for YAML **syntax** errors only (malformed YAML that cannot be parsed). It does not validate against the Runsight workflow schema — for example, it will not catch a misspelled block type or a missing required field. A JSON schema file (`runsight-workflow-schema.json`) is generated from the Pydantic models but is not yet wired into Monaco for autocomplete or schema-level validation.
:::

## Syncing with the canvas store

Every edit in the YAML editor updates the canvas Zustand store in real time:

1. You type in the editor
2. The `onChange` handler fires
3. The new YAML content is written to `useCanvasStore.setYamlContent()`
4. The store parses block counts and edge counts from the YAML
5. The status bar updates to show the current block and edge counts

This means the store always reflects the latest YAML content, even before you save. The `isDirty` flag is set to `true` on the first edit, and the topbar shows an unsaved-changes indicator (a small dot next to the save button).

## Saving your work

Saving a workflow commits it to git. When you click the Save button (or press Cmd+S / Ctrl+S):

1. The commit dialog opens
2. You enter a commit message
3. Runsight writes the YAML file to `custom/workflows/{id}.yaml`
4. If canvas state exists, the sidecar JSON is written alongside it
5. The changes are committed to the main branch

After a successful commit, the `isDirty` flag resets and the unsaved indicator disappears.

## Read-only mode

When viewing a run's historical YAML (in the Run Detail view), the editor opens in read-only mode. The `readOnly` option is passed to Monaco, which disables all editing. The editor still provides syntax highlighting and scrolling, but the cursor cannot modify content.

The historical YAML shown in a run is retrieved from the git commit that was active when the run executed — not the current workflow file. This means you always see exactly the YAML that produced the run's results, even if the workflow has been modified since.

## Editor configuration

The YAML editor uses these Monaco settings:

| Setting | Value |
|---------|-------|
| Language | `yaml` |
| Theme | `runsight-yaml` (custom, reads from CSS variables) |
| Read-only | `false` in edit mode, `true` in readonly/sim |
| Height | `100%` (fills the available surface area) |

The Monaco editor is lazy-loaded — the bundle is split into a separate chunk and loaded on demand when you first open the YAML tab. This keeps the initial page load fast.

## Working alongside the canvas

The YAML editor and canvas are two views of the same workflow state. When both are wired:

- Editing YAML updates the canvas store, which drives the canvas node rendering
- Moving nodes on the canvas updates the sidecar coordinates but does not touch the YAML (layout is stored separately)
- The compiler can regenerate YAML from the canvas graph, preserving execution semantics while stripping visual metadata

Currently, the primary authoring flow is YAML-first: you write YAML in the editor, and the canvas store parses it for counts and metadata. The reverse direction (canvas edits generating YAML) is built in the compiler but the visual canvas is not yet the primary editing surface.

<!-- Linear: RUN-649, RUN-748, RUN-749, Visual Workflow Builder project — last verified against codebase 2026-04-07 -->
