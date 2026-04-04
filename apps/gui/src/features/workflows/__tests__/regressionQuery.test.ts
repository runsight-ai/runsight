import { describe, expect, it } from "vitest";

import {
  WorkflowRegressionSchema,
  WorkflowRegressionsResponseSchema,
} from "../../../types/schemas/regressions";

// ---------------------------------------------------------------------------
// Schema validation — ensures the regression type contract is correct
// ---------------------------------------------------------------------------

describe("WorkflowRegressionSchema", () => {
  it("parses a valid assertion regression", () => {
    const input = { type: "assertion", node_name: "Quality Review" };
    const result = WorkflowRegressionSchema.parse(input);
    expect(result.type).toBe("assertion");
    expect(result.node_name).toBe("Quality Review");
  });

  it("parses a cost_spike regression with delta_pct", () => {
    const input = { type: "cost_spike", node_name: "Writer", delta_pct: 34 };
    const result = WorkflowRegressionSchema.parse(input);
    expect(result.type).toBe("cost_spike");
    expect(result.node_name).toBe("Writer");
    expect(result.delta_pct).toBe(34);
  });

  it("parses a latency_spike regression with delta_pct", () => {
    const input = {
      type: "latency_spike",
      node_name: "Summarizer",
      delta_pct: 120,
    };
    const result = WorkflowRegressionSchema.parse(input);
    expect(result.type).toBe("latency_spike");
    expect(result.delta_pct).toBe(120);
  });

  it("allows delta_pct to be optional for assertion type", () => {
    const input = { type: "assertion", node_name: "Validator" };
    const result = WorkflowRegressionSchema.parse(input);
    expect(result.delta_pct).toBeUndefined();
  });

  it("rejects unknown regression type", () => {
    const input = { type: "unknown_type", node_name: "Foo" };
    expect(() => WorkflowRegressionSchema.parse(input)).toThrow();
  });

  it("rejects missing node_name", () => {
    const input = { type: "assertion" };
    expect(() => WorkflowRegressionSchema.parse(input)).toThrow();
  });
});

describe("WorkflowRegressionsResponseSchema", () => {
  it("parses a valid response with items array and count", () => {
    const input = {
      workflow_id: "wf-123",
      items: [
        { type: "assertion", node_name: "Quality Review" },
        { type: "cost_spike", node_name: "Writer", delta_pct: 34 },
      ],
      count: 2,
    };
    const result = WorkflowRegressionsResponseSchema.parse(input);
    expect(result.workflow_id).toBe("wf-123");
    expect(result.items).toHaveLength(2);
    expect(result.count).toBe(2);
  });

  it("parses an empty regressions response", () => {
    const input = {
      workflow_id: "wf-456",
      items: [],
      count: 0,
    };
    const result = WorkflowRegressionsResponseSchema.parse(input);
    expect(result.items).toEqual([]);
    expect(result.count).toBe(0);
  });

  it("rejects response missing workflow_id", () => {
    const input = {
      items: [{ type: "assertion", node_name: "X" }],
      count: 1,
    };
    expect(() => WorkflowRegressionsResponseSchema.parse(input)).toThrow();
  });
});

// ---------------------------------------------------------------------------
// API method contract — workflowsApi.getWorkflowRegressions
// ---------------------------------------------------------------------------

describe("workflowsApi.getWorkflowRegressions", () => {
  it("is exported as a function from the workflows API module", async () => {
    // Dynamic import so the test file itself compiles even if the module
    // doesn't exist yet — the test will fail at runtime with a clear message.
    const { workflowsApi } = await import("../../../api/workflows");
    expect(typeof workflowsApi.getWorkflowRegressions).toBe("function");
  });
});

// ---------------------------------------------------------------------------
// Query key contract — queryKeys.workflows.regressions
// ---------------------------------------------------------------------------

describe("queryKeys.workflows.regressions", () => {
  it("produces a namespaced key tuple with workflow id", async () => {
    const { queryKeys } = await import("../../../queries/keys");
    const key = queryKeys.workflows.regressions("wf-123");
    expect(key).toEqual(["workflows", "wf-123", "regressions"]);
  });
});

// ---------------------------------------------------------------------------
// Hook contract — useWorkflowRegressions
// ---------------------------------------------------------------------------

describe("useWorkflowRegressions export", () => {
  it("is exported from the workflows queries module", async () => {
    const mod = await import("../../../queries/workflows");
    expect(typeof mod.useWorkflowRegressions).toBe("function");
  });
});
