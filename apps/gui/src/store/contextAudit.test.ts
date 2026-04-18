import { beforeEach, describe, expect, it } from "vitest";
import type { ContextAuditEventV1 } from "@runsight/shared/zod";
import {
  selectContextAuditEdges,
  selectContextAuditRows,
  selectNodeEvents,
  selectNodeSummary,
  selectRunEvents,
  selectRunSummary,
  useContextAuditStore,
} from "./contextAudit";

function event(
  runId: string,
  nodeId: string,
  sequence: number | null,
  overrides: Partial<ContextAuditEventV1> = {},
): ContextAuditEventV1 {
  return {
    schema_version: "context_audit.v1",
    event: "context_resolution",
    run_id: runId,
    workflow_name: "wf",
    node_id: nodeId,
    block_type: "linear",
    access: "declared",
    mode: "strict",
    sequence,
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
        preview: "bounded",
        reason: null,
        internal: false,
      },
    ],
    resolved_count: 1,
    denied_count: 0,
    warning_count: 0,
    emitted_at: `2026-04-17T00:00:0${sequence ?? 0}.000Z`,
    ...overrides,
  };
}

describe("useContextAuditStore", () => {
  beforeEach(() => {
    useContextAuditStore.getState().clearRun("run_a");
    useContextAuditStore.getState().clearRun("run_b");
  });

  it("replaceRunEvents sets the active run and clears previous run state", async () => {
    const store = useContextAuditStore.getState();

    store.replaceRunEvents("run_a", [event("run_a", "a", 1)]);
    store.replaceRunEvents("run_b", [event("run_b", "b", 1)]);

    const state = useContextAuditStore.getState();
    expect(state.activeRunId).toBe("run_b");
    expect(selectRunEvents("run_a")(state)).toEqual([]);
    expect(selectRunEvents("run_b")(state).map((item) => item.node_id)).toEqual(["b"]);
  });

  it("appendEvents preserves history order, appends live events, and ignores wrong runs", async () => {
    const store = useContextAuditStore.getState();

    store.replaceRunEvents("run_a", [event("run_a", "draft", 1)]);
    store.appendEvents("run_a", [
      event("run_a", "review", 2),
      event("run_other", "leak", 3),
    ]);

    const events = selectRunEvents("run_a")(useContextAuditStore.getState());
    expect(events.map((item) => `${item.node_id}:${item.sequence}`)).toEqual([
      "draft:1",
      "review:2",
    ]);
  });

  it("dedupes duplicate run_id:sequence events from history and SSE", async () => {
    const store = useContextAuditStore.getState();

    store.replaceRunEvents("run_a", [event("run_a", "draft", 7)]);
    store.appendEvents("run_a", [event("run_a", "draft", 7)]);

    expect(selectRunEvents("run_a")(useContextAuditStore.getState())).toHaveLength(1);
  });

  it("uses deterministic fallback dedupe when sequence is null", async () => {
    const fallbackEvent = event("run_a", "draft", null, {
      emitted_at: "2026-04-17T01:00:00.000Z",
    });

    useContextAuditStore.getState().replaceRunEvents("run_a", [fallbackEvent]);
    useContextAuditStore.getState().appendEvents("run_a", [{ ...fallbackEvent }]);

    expect(selectRunEvents("run_a")(useContextAuditStore.getState())).toHaveLength(1);
  });

  it("selectors produce run and node summaries, rows, and data-flow edges", async () => {
    const warningEvent = event("run_a", "review", 2, {
      records: [
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
      resolved_count: 0,
      warning_count: 1,
    });

    useContextAuditStore.getState().replaceRunEvents("run_a", [
      event("run_a", "draft", 1),
      warningEvent,
    ]);
    const state = useContextAuditStore.getState();

    expect(selectNodeEvents("run_a", "review")(state)).toHaveLength(1);
    expect(selectRunSummary("run_a")(state)).toMatchObject({
      totalEvents: 2,
      resolvedCount: 1,
      warningCount: 1,
    });
    expect(selectNodeSummary("run_a", "review")(state)).toMatchObject({
      totalEvents: 1,
      inputCount: 1,
      warningCount: 1,
    });
    expect(selectContextAuditRows("run_a")(state)).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          runId: "run_a",
          nodeId: "review",
          inputName: "api_key",
          status: "missing",
          severity: "warn",
        }),
      ]),
    );
    expect(selectContextAuditEdges("run_a")(state)).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          runId: "run_a",
          source: "draft",
          target: "draft",
          inputName: "summary",
          namespace: "results",
        }),
      ]),
    );
  });
});
