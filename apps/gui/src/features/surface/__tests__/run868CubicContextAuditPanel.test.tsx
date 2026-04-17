// @vitest-environment jsdom

import React from "react";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ContextAuditEventV1 } from "@runsight/shared/zod";

import { useContextAuditStore } from "@/store/contextAudit";
import { ContextAuditPanel } from "../contextAuditSurfaces";

function contextEvent(
  runId: string,
  nodeId: string,
  sequence: number,
): ContextAuditEventV1 {
  return {
    schema_version: "context_audit.v1",
    event: "context_resolution",
    run_id: runId,
    workflow_name: "workflow",
    node_id: nodeId,
    block_type: "linear",
    access: "declared",
    mode: "strict",
    sequence,
    records: [
      {
        input_name: `input-${sequence}`,
        from_ref: `source.value_${sequence}`,
        namespace: "results",
        source: "source",
        field_path: `value_${sequence}`,
        status: "resolved",
        severity: "allow",
        value_type: "str",
        preview: `value ${sequence}`,
        reason: null,
        internal: false,
      },
    ],
    resolved_count: 1,
    denied_count: 0,
    warning_count: 0,
    emitted_at: "2026-04-17T10:00:00.000Z",
  };
}

function makeEvents(runId: string, prefix: string, start: number, count: number) {
  return Array.from({ length: count }, (_, offset) => {
    const index = start + offset;
    return contextEvent(runId, `${prefix}-${index}`, index + 1);
  });
}

describe("RUN-868 context audit pagination regressions", () => {
  beforeEach(() => {
    useContextAuditStore.setState({ activeRunId: null, eventsByRun: {} });
  });

  afterEach(() => {
    cleanup();
  });

  it("resets visible rows when the selected run changes", async () => {
    const user = userEvent.setup();
    useContextAuditStore.setState({
      activeRunId: "run-a",
      eventsByRun: {
        "run-a": makeEvents("run-a", "node-a", 0, 150),
        "run-b": makeEvents("run-b", "node-b", 0, 150),
      },
    });

    const { rerender } = render(
      <ContextAuditPanel
        runId="run-a"
        selectedNodeId={null}
        onSelectNode={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Load more" }));
    expect(screen.getByText("node-a-149")).toBeTruthy();

    rerender(
      <ContextAuditPanel
        runId="run-b"
        selectedNodeId={null}
        onSelectNode={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.queryByText("node-b-149")).toBeNull();
    });
    expect(screen.getByText("node-b-99")).toBeTruthy();
  });

  it("shows rows fetched from the next remote page immediately", async () => {
    const user = userEvent.setup();
    useContextAuditStore.getState().replaceRunEvents(
      "run-c",
      makeEvents("run-c", "node-c", 0, 100),
    );
    const fetchNextPage = vi.fn(async () => {
      useContextAuditStore.getState().appendEvents(
        "run-c",
        makeEvents("run-c", "node-c", 100, 50),
      );
    });

    render(
      <ContextAuditPanel
        runId="run-c"
        selectedNodeId={null}
        onSelectNode={vi.fn()}
        fetchNextPage={fetchNextPage}
        hasNextPage
      />,
    );

    expect(screen.queryByText("node-c-149")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Load more" }));

    await waitFor(() => {
      expect(screen.getByText("node-c-149")).toBeTruthy();
    });
    expect(fetchNextPage).toHaveBeenCalledTimes(1);
  });
});
