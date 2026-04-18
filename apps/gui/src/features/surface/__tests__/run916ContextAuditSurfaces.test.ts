import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { beforeEach, describe, expect, it } from "vitest";
import type { ContextAuditEventV1 } from "@runsight/shared/zod";

import {
  selectContextAuditEdges,
  useContextAuditStore,
} from "@/store/contextAudit";

const GUI_SRC = "/Users/nataly/Documents/github/runsight/apps/gui/src";

function readSource(...parts: string[]) {
  return readFileSync(resolve(GUI_SRC, ...parts), "utf8");
}

function readOptionalSource(...parts: string[]) {
  const path = resolve(GUI_SRC, ...parts);
  return existsSync(path) ? readFileSync(path, "utf8") : "";
}

const bottomPanelSource = readSource("features", "surface", "SurfaceBottomPanel.tsx");
const inspectorSource = readSource("features", "surface", "SurfaceInspectorPanel.tsx");
const nodeCardSource = readSource(
  "features",
  "surface",
  "nodes",
  "SurfaceNodeCard.tsx",
);
const canvasSource = readSource("features", "surface", "SurfaceCanvas.tsx");
const workflowSurfaceSource = readSource("features", "surface", "WorkflowSurface.tsx");
const optionalSurfaceSource = [
  readOptionalSource("features", "surface", "ContextAuditPanel.tsx"),
  readOptionalSource("features", "surface", "ContextInspectorTab.tsx"),
  readOptionalSource("features", "surface", "ContextAccessBadge.tsx"),
  readOptionalSource("features", "surface", "ContextResolutionBadge.tsx"),
  readOptionalSource("features", "surface", "contextAuditSurfaces.tsx"),
  readOptionalSource("features", "surface", "contextAuditSurfaces.ts"),
].join("\n");
const surfaceSource = [
  bottomPanelSource,
  inspectorSource,
  nodeCardSource,
  canvasSource,
  workflowSurfaceSource,
  optionalSurfaceSource,
].join("\n");

function auditEvent(
  overrides: Partial<ContextAuditEventV1> = {},
): ContextAuditEventV1 {
  return {
    schema_version: "context_audit.v1",
    event: "context_resolution",
    run_id: "run-916",
    workflow_name: "workflow",
    node_id: "summarize",
    block_type: "linear",
    access: "declared",
    mode: "strict",
    sequence: 1,
    records: [
      {
        input_name: "summary",
        from_ref: "draft.summary",
        namespace: "results",
        source: "draft",
        field_path: "summary",
        status: "resolved",
        severity: "allow",
        value_type: "str",
        preview: "short version",
        reason: null,
        internal: false,
      },
      {
        input_name: "reason",
        from_ref: "workflow.reason",
        namespace: "results",
        source: "workflow",
        field_path: "reason",
        status: "resolved",
        severity: "allow",
        value_type: "str",
        preview: "seeded input",
        reason: null,
        internal: false,
      },
      {
        input_name: "api_key",
        from_ref: "metadata.credentials.api_key",
        namespace: "metadata",
        source: "credentials",
        field_path: "api_key",
        status: "missing",
        severity: "warn",
        value_type: null,
        preview: "[redacted]",
        reason: "missing",
        internal: false,
      },
    ],
    resolved_count: 2,
    denied_count: 0,
    warning_count: 1,
    emitted_at: "2026-04-17T10:00:00.000Z",
    ...overrides,
  };
}

describe("RUN-916 context audit surface contracts", () => {
  it("adds a bottom-panel Audit tab that owns rows, pagination, and keyboard row activation", () => {
    expect(bottomPanelSource).toMatch(/activeTab[\s\S]{0,120}audit/);
    expect(bottomPanelSource).toContain("workflow-audit-tab");
    expect(bottomPanelSource).toContain("ContextAuditPanel");

    expect(surfaceSource).toMatch(/type ContextAuditPanelProps|interface ContextAuditPanelProps/);
    expect(surfaceSource).toContain("runId");
    expect(surfaceSource).toContain("selectedNodeId");
    expect(surfaceSource).toContain("onSelectNode");

    expect(surfaceSource).toContain("status");
    expect(surfaceSource).toContain("severity");
    expect(surfaceSource).toContain("resolved");
    expect(surfaceSource).toContain("allow");
    expect(surfaceSource).toContain("missing");
    expect(surfaceSource).toContain("warn");

    expect(surfaceSource).toMatch(/fetchNextPage|loadMore|Load more/);
    expect(surfaceSource).toMatch(/onKeyDown[\s\S]{0,180}(Enter| )/);
    expect(surfaceSource).toMatch(/truncate|break-all|overflow-hidden/);
  });

  it("wires audit row selection to node selection and the inspector Context tab", () => {
    expect(inspectorSource).toMatch(/activeTab[\s\S]{0,120}context/);
    expect(inspectorSource).toContain("ContextInspectorTab");
    expect(surfaceSource).toMatch(
      /type ContextInspectorTabProps|interface ContextInspectorTabProps/,
    );
    expect(surfaceSource).toContain("events");

    const rowSelectionOwner = `${bottomPanelSource}\n${workflowSurfaceSource}`;
    expect(rowSelectionOwner).toMatch(/selectNode|selectedNodeId/);
    expect(rowSelectionOwner).toMatch(/setInspectorTab|requestedTab|initialTab/);
    expect(rowSelectionOwner).toMatch(/context/);
  });

  it("renders node-level access and resolution badges with text labels", () => {
    expect(nodeCardSource).toContain("ContextAccessBadge");
    expect(nodeCardSource).toContain("ContextResolutionBadge");
    expect(surfaceSource).toMatch(/type ContextAccessBadgeProps|interface ContextAccessBadgeProps/);
    expect(surfaceSource).toMatch(
      /type ContextResolutionBadgeProps|interface ContextResolutionBadgeProps/,
    );

    expect(surfaceSource).not.toContain(`Access ${"all"}`);
    expect(surfaceSource).toContain("Access declared");
    expect(surfaceSource).toMatch(/warning|Warning|warn/);
    expect(surfaceSource).toMatch(/denied|Denied|error/);
    expect(surfaceSource).toMatch(/min-w|w-\[|h-\[/);
    expect(surfaceSource).toMatch(/--warning-|--danger-|--info-|--success-/);
  });

  it("derives non-persisted context overlay edges in SurfaceCanvas only", () => {
    expect(canvasSource).toContain("selectContextAuditEdges");
    expect(canvasSource).toContain("context-overlay");
    expect(canvasSource).toMatch(/source\s*!==\s*["']workflow["']/);
    expect(canvasSource).toMatch(/namespace\s*={0,2}\s*["']results["']/);
    expect(canvasSource).toMatch(/edges=\{\[[\s\S]*edges[\s\S]*context/);
    expect(canvasSource).toContain("selectable: false");
    expect(canvasSource).toContain("focusable: false");
    expect(canvasSource).toContain("deletable: false");
    expect(canvasSource).toContain("reconnectable: false");
    expect(canvasSource).not.toMatch(/setEdges\([^)]*context/i);
  });

  it("passes the selected audit run id into canvas and inspector context views", () => {
    expect(workflowSurfaceSource).toContain("contextRunId");
    expect(workflowSurfaceSource).toContain("setInspectedRunId");
    expect(workflowSurfaceSource).toMatch(/runId=\{p\.contextRunId\}/);
    expect(workflowSurfaceSource).toMatch(/onAuditNodeSelect=\{\(nodeId, runId\)/);
    expect(workflowSurfaceSource).toContain("setInspectedRunId(readonlyRunId || undefined)");
    expect(workflowSurfaceSource).not.toContain("setInspectedRunId(contextRunId || undefined)");
  });
});

describe("RUN-916 context audit overlay inputs", () => {
  beforeEach(() => {
    useContextAuditStore.setState({ activeRunId: null, eventsByRun: {} });
  });

  it("creates overlay edge inputs only for results records with canvas node sources", () => {
    useContextAuditStore.getState().replaceRunEvents("run-916", [auditEvent()]);

    const edges = selectContextAuditEdges("run-916")(useContextAuditStore.getState());

    expect(edges).toEqual([
      expect.objectContaining({
        runId: "run-916",
        source: "draft",
        target: "summarize",
        inputName: "summary",
        namespace: "results",
      }),
    ]);
    expect(edges).not.toEqual(
      expect.arrayContaining([
        expect.objectContaining({ source: "workflow" }),
        expect.objectContaining({ namespace: "metadata" }),
      ]),
    );
  });
});
