import { describe, expect, it } from "vitest";

import {
  WorkflowRegressionSchema,
  WorkflowRegressionsResponseSchema,
} from "../../../types/schemas/regressions";

// ---------------------------------------------------------------------------
// Schema validation — ensures the regression type contract is correct
// ---------------------------------------------------------------------------

describe("WorkflowRegressionSchema", () => {
  it("parses a valid assertion_regression", () => {
    const input = {
      node_id: "node-1",
      node_name: "Quality Review",
      type: "assertion_regression",
      delta: { eval_passed: false, baseline_eval_passed: true },
    };
    const result = WorkflowRegressionSchema.parse(input);
    expect(result.type).toBe("assertion_regression");
    expect(result.node_name).toBe("Quality Review");
    expect(result.node_id).toBe("node-1");
  });

  it("parses a cost_spike regression with delta record", () => {
    const input = {
      node_id: "node-2",
      node_name: "Writer",
      type: "cost_spike",
      delta: { cost_pct: 34, baseline_cost: 0.05 },
    };
    const result = WorkflowRegressionSchema.parse(input);
    expect(result.type).toBe("cost_spike");
    expect(result.node_name).toBe("Writer");
    expect(result.delta).toEqual({ cost_pct: 34, baseline_cost: 0.05 });
  });

  it("parses a quality_drop regression with delta record", () => {
    const input = {
      node_id: "node-3",
      node_name: "Summarizer",
      type: "quality_drop",
      delta: { score_delta: -0.2 },
    };
    const result = WorkflowRegressionSchema.parse(input);
    expect(result.type).toBe("quality_drop");
    expect(result.delta).toEqual({ score_delta: -0.2 });
  });

  it("accepts optional run_id and run_number fields", () => {
    const input = {
      node_id: "node-4",
      node_name: "Validator",
      type: "assertion_regression",
      delta: {},
      run_id: "run-1",
      run_number: 5,
    };
    const result = WorkflowRegressionSchema.parse(input);
    expect(result.run_id).toBe("run-1");
    expect(result.run_number).toBe(5);
  });

  it("rejects unknown regression type", () => {
    const input = {
      node_id: "node-5",
      node_name: "Foo",
      type: "unknown_type",
      delta: {},
    };
    expect(() => WorkflowRegressionSchema.parse(input)).toThrow();
  });

  it("rejects missing node_name", () => {
    const input = {
      node_id: "node-6",
      type: "assertion_regression",
      delta: {},
    };
    expect(() => WorkflowRegressionSchema.parse(input)).toThrow();
  });
});

describe("WorkflowRegressionsResponseSchema", () => {
  it("parses a valid response with issues array and count", () => {
    const input = {
      issues: [
        {
          node_id: "node-1",
          node_name: "Quality Review",
          type: "assertion_regression",
          delta: { eval_passed: false },
        },
        {
          node_id: "node-2",
          node_name: "Writer",
          type: "cost_spike",
          delta: { cost_pct: 34 },
        },
      ],
      count: 2,
    };
    const result = WorkflowRegressionsResponseSchema.parse(input);
    expect(result.issues).toHaveLength(2);
    expect(result.count).toBe(2);
  });

  it("parses an empty regressions response", () => {
    const input = {
      issues: [],
      count: 0,
    };
    const result = WorkflowRegressionsResponseSchema.parse(input);
    expect(result.issues).toEqual([]);
    expect(result.count).toBe(0);
  });

  it("rejects response missing count", () => {
    const input = {
      issues: [
        {
          node_id: "node-1",
          node_name: "X",
          type: "assertion_regression",
          delta: {},
        },
      ],
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
