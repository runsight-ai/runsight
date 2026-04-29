import { beforeEach, describe, expect, it } from "vitest";
import {
  ContextAuditEventV1Schema,
  ContextAuditListResponseSchema,
  type ContextAuditEventV1,
} from "@runsight/shared/zod";

import {
  selectContextAuditRows,
  selectRunEvents,
  useContextAuditStore,
} from "@/store/contextAudit";

function auditEvent(overrides: Partial<ContextAuditEventV1> = {}): ContextAuditEventV1 {
  return {
    schema_version: "context_audit.v1",
    event: "context_resolution",
    run_id: "run_context_audit",
    workflow_name: "context_governance_integration",
    node_id: "review",
    block_type: "linear",
    access: "declared",
    mode: "strict",
    sequence: 17,
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
        preview: "safe draft",
        reason: null,
        internal: false,
      },
    ],
    resolved_count: 1,
    denied_count: 0,
    warning_count: 0,
    emitted_at: "2026-04-17T00:00:17.000Z",
    ...overrides,
  };
}

describe("context audit GUI contract integration", () => {
  beforeEach(() => {
    useContextAuditStore.getState().clearRun("run_context_audit");
  });

  it("accepts identical historical endpoint and SSE payloads through generated schemas and store", () => {
    const historicalPayload = ContextAuditListResponseSchema.parse({
      items: [auditEvent()],
      page_size: 1,
      has_next_page: false,
      end_cursor: null,
    });
    const ssePayload = ContextAuditEventV1Schema.parse(JSON.parse(JSON.stringify(auditEvent())));

    expect(ssePayload).toEqual(historicalPayload.items[0]);

    useContextAuditStore.getState().replaceRunEvents("run_context_audit", historicalPayload.items);
    useContextAuditStore.getState().appendEvents("run_context_audit", [ssePayload]);

    const state = useContextAuditStore.getState();
    expect(selectRunEvents("run_context_audit")(state)).toHaveLength(1);
    expect(selectContextAuditRows("run_context_audit")(state)).toEqual([
      {
        id: "run_context_audit:17:0",
        runId: "run_context_audit",
        nodeId: "review",
        blockType: "linear",
        access: "declared",
        sequence: 17,
        emittedAt: "2026-04-17T00:00:17.000Z",
        inputName: "summary",
        fromRef: "draft.summary",
        status: "resolved",
        severity: "allow",
        internal: false,
      },
    ]);
  });
});
