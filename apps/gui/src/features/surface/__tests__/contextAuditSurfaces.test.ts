// @vitest-environment jsdom

import React from "react";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ContextAuditEventV1 } from "@runsight/shared/zod";

import {
  selectContextAuditEdges,
  useContextAuditStore,
} from "@/store/contextAudit";
import { useCanvasStore } from "@/store/canvas";
import { SurfaceCanvas } from "../SurfaceCanvas";
import {
  ContextAuditPanel,
  ContextInspectorTab,
} from "../contextAuditSurfaces";
import { SoulNode } from "../nodes";

const LONG_REF =
  "secrets.customer_accounts.production.credentials.primary.api_key.rotated.current.value";

const reactFlowHarness = vi.hoisted(() => ({
  props: null as { edges?: Array<Record<string, unknown>> } | null,
}));

vi.mock("@xyflow/react", async () => {
  const ReactModule = await import("react");
  return {
    ReactFlow: (props: { children?: React.ReactNode; edges?: Array<Record<string, unknown>> }) => {
      reactFlowHarness.props = props;
      return ReactModule.createElement("div", { "data-testid": "react-flow" }, props.children);
    },
    Background: () => null,
    Controls: () => null,
    MiniMap: () => null,
    Handle: () => null,
    BackgroundVariant: { Dots: "dots" },
    Position: { Left: "left", Right: "right" },
    applyEdgeChanges: (_changes: unknown, edges: unknown[]) => edges,
    applyNodeChanges: (_changes: unknown, nodes: unknown[]) => nodes,
  };
});

function auditEvent(
  overrides: Partial<ContextAuditEventV1> = {},
): ContextAuditEventV1 {
  return {
    schema_version: "context_audit.v1",
    event: "context_resolution",
    run_id: "run-context-surface",
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

function deniedAuditEvent(
  overrides: Partial<ContextAuditEventV1> = {},
): ContextAuditEventV1 {
  return auditEvent({
    node_id: "strict_missing",
    sequence: 2,
    records: [
      {
        input_name: "api_key",
        from_ref: LONG_REF,
        namespace: "metadata",
        source: "secrets",
        field_path: "customer_accounts.production.credentials.primary.api_key.value",
        status: "denied",
        severity: "error",
        value_type: null,
        preview: "[redacted]",
        reason: "strict declared ref denied",
        internal: false,
      },
    ],
    resolved_count: 0,
    denied_count: 1,
    warning_count: 0,
    ...overrides,
  });
}

describe("context audit overlay inputs", () => {
  beforeEach(() => {
    useContextAuditStore.setState({ activeRunId: null, eventsByRun: {} });
    useCanvasStore.getState().reset();
    reactFlowHarness.props = null;
  });

  afterEach(() => {
    cleanup();
  });

  it("creates overlay edge inputs only for results records with canvas node sources", () => {
    useContextAuditStore.getState().replaceRunEvents("run-context-surface", [auditEvent()]);

    const edges = selectContextAuditEdges("run-context-surface")(useContextAuditStore.getState());

    expect(edges).toEqual([
      expect.objectContaining({
        runId: "run-context-surface",
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

  it("renders audit rows and activates node selection by mouse and keyboard", async () => {
    const user = userEvent.setup();
    const onSelectNode = vi.fn();
    useContextAuditStore.getState().replaceRunEvents("run-context-surface", [auditEvent()]);

    render(
      React.createElement(ContextAuditPanel, {
        runId: "run-context-surface",
        selectedNodeId: null,
        onSelectNode,
      }),
    );

    const rows = screen.getAllByRole("button", {
      name: "Open context audit for summarize",
    });
    expect(rows).toHaveLength(3);
    expect(within(rows[0]).getByText("summary")).toBeTruthy();
    expect(within(rows[0]).getByText("draft.summary")).toBeTruthy();
    expect(within(rows[2]).getByText("missing")).toBeTruthy();
    expect(within(rows[2]).getByText("warn")).toBeTruthy();

    await user.click(rows[0]);
    expect(onSelectNode).toHaveBeenLastCalledWith("summarize");

    rows[1].focus();
    await user.keyboard("{Enter}");
    expect(onSelectNode).toHaveBeenCalledTimes(2);
    expect(onSelectNode).toHaveBeenLastCalledWith("summarize");
  });

  it("renders denied rows with error severity and long references", () => {
    useContextAuditStore
      .getState()
      .replaceRunEvents("run-context-surface", [auditEvent(), deniedAuditEvent()]);

    render(
      React.createElement(ContextAuditPanel, {
        runId: "run-context-surface",
        selectedNodeId: null,
        onSelectNode: vi.fn(),
      }),
    );

    const strictRows = screen.getAllByRole("button", {
      name: "Open context audit for strict_missing",
    });
    expect(strictRows).toHaveLength(1);
    expect(within(strictRows[0]).getByText("api_key")).toBeTruthy();
    expect(within(strictRows[0]).getByText(LONG_REF)).toBeTruthy();
    expect(within(strictRows[0]).getByText("denied")).toBeTruthy();
    expect(within(strictRows[0]).getByText("error")).toBeTruthy();
  });

  it("renders inspector context records with access and resolution badges", () => {
    render(React.createElement(ContextInspectorTab, { events: [auditEvent()] }));

    expect(screen.getByText("Access declared")).toBeTruthy();
    expect(screen.getByText("Warning 1")).toBeTruthy();
    expect(screen.getByText("2 resolved · 1 warning · 0 denied")).toBeTruthy();
    expect(screen.getByText("draft.summary")).toBeTruthy();
    expect(screen.getByText("[redacted]")).toBeTruthy();
  });

  it("renders inspector denied records with error severity", () => {
    render(React.createElement(ContextInspectorTab, { events: [deniedAuditEvent()] }));

    expect(screen.getByText("Access declared")).toBeTruthy();
    expect(screen.getByText("Denied 1")).toBeTruthy();
    expect(screen.getByText("0 resolved · 0 warning · 1 denied")).toBeTruthy();
    expect(screen.getByText(LONG_REF)).toBeTruthy();
    expect(screen.getByText("denied")).toBeTruthy();
    expect(screen.getByText("error")).toBeTruthy();
  });

  it("renders node-level context badges for the active audit run", () => {
    useContextAuditStore.getState().replaceRunEvents("run-context-surface", [auditEvent()]);

    render(
      React.createElement(SoulNode as React.ComponentType<Record<string, unknown>>, {
        id: "summarize",
        selected: false,
        data: {
          name: "Summarize",
          status: "completed",
          stepType: "linear",
          soulRef: "writer",
        },
      }),
    );

    expect(screen.getByText("Access declared")).toBeTruthy();
    expect(screen.getByText("Warning 1")).toBeTruthy();
  });

  it("renders node-level denied context badges for the active audit run", () => {
    useContextAuditStore.getState().replaceRunEvents("run-context-surface", [deniedAuditEvent()]);

    render(
      React.createElement(SoulNode as React.ComponentType<Record<string, unknown>>, {
        id: "strict_missing",
        selected: false,
        data: {
          name: "Strict Missing",
          status: "failed",
          stepType: "linear",
          soulRef: "writer",
        },
      }),
    );

    expect(screen.getByText("Access declared")).toBeTruthy();
    expect(screen.getByText("Denied 1")).toBeTruthy();
  });

  it("adds non-persisted context overlay edges to the rendered canvas only", () => {
    useCanvasStore.getState().setNodes(
      [
        {
          id: "draft",
          type: "soul",
          position: { x: 0, y: 0 },
          data: { name: "Draft", status: "idle", stepType: "linear" },
        },
        {
          id: "summarize",
          type: "soul",
          position: { x: 200, y: 0 },
          data: { name: "Summarize", status: "idle", stepType: "linear" },
        },
      ],
      false,
    );
    useCanvasStore.getState().setEdges(
      [{ id: "persisted-edge", source: "draft", target: "summarize" }],
      false,
    );
    useContextAuditStore.getState().replaceRunEvents("run-context-surface", [auditEvent()]);

    render(React.createElement(SurfaceCanvas, { runId: "run-context-surface" }));

    const edges = reactFlowHarness.props?.edges ?? [];
    expect(edges).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ id: "persisted-edge" }),
        expect.objectContaining({
          id: "context-overlay:run-context-surface:1:0:edge",
          source: "draft",
          target: "summarize",
          type: "straight",
          className: "context-overlay",
          label: "summary",
          selectable: false,
          focusable: false,
          deletable: false,
          reconnectable: false,
          data: { context: true, namespace: "results" },
        }),
      ]),
    );
    expect(edges).not.toEqual(
      expect.arrayContaining([
        expect.objectContaining({ source: "workflow" }),
        expect.objectContaining({ data: { context: true, namespace: "metadata" } }),
      ]),
    );
    expect(useCanvasStore.getState().edges).toEqual([
      { id: "persisted-edge", source: "draft", target: "summarize" },
    ]);
  });
});
