import { beforeEach, describe, expect, it, vi } from "vitest";

const { apiGet } = vi.hoisted(() => ({
  apiGet: vi.fn(),
}));

vi.mock("../client", () => ({
  api: {
    get: apiGet,
  },
}));

import { runsApi } from "../runs";

const validContextAuditResponse = {
  items: [
    {
      schema_version: "context_audit.v1",
      event: "context_resolution",
      run_id: "run_context_contract",
      workflow_name: "wf",
      node_id: "summarize",
      block_type: "linear",
      access: "declared",
      mode: "strict",
      sequence: 1,
      records: [],
      resolved_count: 0,
      denied_count: 0,
      warning_count: 0,
      emitted_at: new Date("2026-01-01T00:00:00.000Z").toISOString(),
    },
  ],
  page_size: 100,
  has_next_page: false,
  end_cursor: null,
};

describe("runsApi context audit adapter", () => {
  beforeEach(() => {
    apiGet.mockReset();
  });

  it("requests the context audit endpoint with supported query params", async () => {
    apiGet.mockResolvedValueOnce(validContextAuditResponse);

    await expect(
      runsApi.getRunContextAudit("run_context_contract", {
        node_id: "summarize",
        cursor: "cursor_1",
        page_size: 50,
      }),
    ).resolves.toMatchObject({
      page_size: 100,
      has_next_page: false,
      end_cursor: null,
    });

    expect(apiGet).toHaveBeenCalledWith(
      "/runs/run_context_contract/context-audit?node_id=summarize&cursor=cursor_1&page_size=50",
    );
  });

  it("parses responses with the generated ContextAuditListResponseSchema", async () => {
    apiGet.mockResolvedValueOnce({
      ...validContextAuditResponse,
      page_size: "100",
    });

    await expect(runsApi.getRunContextAudit("run_context_contract")).rejects.toThrow();
  });
});
