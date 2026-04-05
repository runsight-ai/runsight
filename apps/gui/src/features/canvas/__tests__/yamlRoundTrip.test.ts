/**
 * RED-TEAM tests for RUN-120: Round-trip tests + schema conformance.
 *
 * Validates: compile -> parse -> compile is lossless.
 * These tests may FAIL if there are round-trip bugs — that is the point.
 */

import { describe, it, expect, test } from "vitest";
import { compileGraphToWorkflowYaml } from "../yamlCompiler";
import { parseWorkflowYamlToGraph } from "../yamlParser";
import type { StepNodeData, StepType, CaseDef } from "../../../types/schemas/canvas";
import type { Node, Edge } from "@xyflow/react";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function mockNode(
  id: string,
  stepType: StepType,
  extraData: Partial<StepNodeData> = {},
): Node<StepNodeData> {
  return {
    id,
    type: "canvasNode",
    position: { x: 0, y: 0 },
    data: {
      stepId: id,
      name: id,
      stepType,
      status: "idle",
      ...extraData,
    },
  };
}

function mockEdge(
  source: string,
  target: string,
  sourceHandle?: string,
): Edge {
  return {
    id: `${source}->${target}${sourceHandle ? `:${sourceHandle}` : ""}`,
    source,
    target,
    sourceHandle: sourceHandle ?? null,
    targetHandle: null,
  };
}

interface CompileInput {
  nodes: Node<StepNodeData>[];
  edges: Edge[];
  workflowName?: string;
  config?: Record<string, unknown>;
}

/**
 * Core round-trip: compile -> parse -> compile.
 * Returns both YAML strings and compiled documents for assertion.
 */
function roundTrip(input: CompileInput) {
  const { yaml: yaml1, workflowDocument: doc1 } = compileGraphToWorkflowYaml(input);
  const parsed = parseWorkflowYamlToGraph(yaml1);

  // Rebuild compile input from parsed result (souls no longer propagated — RUN-574)
  const input2: CompileInput = {
    nodes: parsed.nodes,
    edges: parsed.edges,
    config: parsed.config,
    workflowName: input.workflowName,
  };
  const { yaml: yaml2, workflowDocument: doc2 } = compileGraphToWorkflowYaml(input2);

  return { yaml1, yaml2, doc1, doc2, parsed };
}

// ===========================================================================
// 1. Per-type round-trip
// ===========================================================================

describe("Per-type round-trip", () => {
  test.each<[string, StepType, Partial<StepNodeData>]>([
    ["linear", "linear", { soulRef: "researcher" }],
    ["dispatch multi-soul", "dispatch", { soulRefs: ["a", "b"] }],
    ["synthesize", "synthesize", { soulRef: "synth", inputBlockIds: ["a", "b"] }],
    ["dispatch conditional-style", "dispatch", { soulRef: "dispatcher" }],
    ["gate", "gate", { soulRef: "gatekeeper", evalKey: "quality", extractField: "score" }],
    ["team_lead", "team_lead", { soulRef: "lead", failureContextKeys: ["err"] }],
    ["engineering_manager", "engineering_manager", { soulRef: "em" }],
    ["file_writer (minimal)", "file_writer", { outputPath: "./out.md", contentKey: "result" }],
    ["file_writer", "file_writer", { outputPath: "./out.md", contentKey: "result" }],
    ["code", "code", { code: "def main():\n  return {}", timeoutSeconds: 30, allowedImports: ["json"] }],
    ["loop", "loop", { innerBlockRefs: ["step_a", "step_b"], maxRounds: 5, breakCondition: "result.done == true" }],
    ["workflow", "workflow", { workflowRef: "sub.yaml", maxDepth: 2 }],
  ])("round-trip: %s", (_label, stepType, fields) => {
    const node = mockNode("block1", stepType, fields);
    const { doc1, doc2 } = roundTrip({ nodes: [node], edges: [] });

    // Block fields should survive the round-trip
    expect(doc2.blocks["block1"]).toEqual(doc1.blocks["block1"]);

    // The compiled block must contain more than just { type } when fields are provided
    const fieldCount = Object.keys(doc1.blocks["block1"]).length;
    expect(fieldCount).toBeGreaterThan(1);
  });
});

// ===========================================================================
// 2. Souls round-trip
// ===========================================================================

describe("Souls round-trip (RUN-574: souls no longer emitted)", () => {
  it("souls are never present in compiled output", () => {
    const { doc1, doc2 } = roundTrip({
      nodes: [mockNode("b1", "linear", { soulRef: "planner" })],
      edges: [],
    });

    expect(doc1).not.toHaveProperty("souls");
    expect(doc2).not.toHaveProperty("souls");
  });

  it("soul_ref on blocks still survives round-trip", () => {
    const { doc1, doc2 } = roundTrip({
      nodes: [mockNode("b1", "linear", { soulRef: "planner" })],
      edges: [],
    });

    expect(doc1.blocks["b1"]).toHaveProperty("soul_ref", "planner");
    expect(doc2.blocks["b1"]).toHaveProperty("soul_ref", "planner");
  });
});

// ===========================================================================
// 3. Config round-trip
// ===========================================================================

describe("Config round-trip", () => {
  it("config survives compile -> parse -> compile", () => {
    const config: Record<string, unknown> = {
      max_concurrency: 4,
      timeout: 300,
      retry_policy: {
        max_retries: 3,
        backoff: { type: "exponential", base_ms: 100 },
      },
    };

    const { doc1, doc2 } = roundTrip({
      nodes: [mockNode("b1", "linear")],
      edges: [],
      config,
    });

    expect(doc2.config).toEqual(doc1.config);
  });

  it("missing config is omitted in both passes", () => {
    const { doc1, doc2 } = roundTrip({
      nodes: [mockNode("b1", "linear")],
      edges: [],
    });

    expect(doc1.config).toBeUndefined();
    expect(doc2.config).toBeUndefined();
  });
});

// ===========================================================================
// 4. Transitions round-trip
// ===========================================================================

describe("Transitions round-trip", () => {
  it("plain transitions survive compile -> parse -> compile", () => {
    const nodes = [
      mockNode("step_a", "linear", { soulRef: "s1" }),
      mockNode("step_b", "linear", { soulRef: "s2" }),
      mockNode("step_c", "linear"),
    ];
    const edges = [
      mockEdge("step_a", "step_b"),
      mockEdge("step_b", "step_c"),
    ];

    const { doc1, doc2 } = roundTrip({ nodes, edges });

    expect(doc2.workflow.transitions).toEqual(doc1.workflow.transitions);
  });

  it("transition ordering is preserved", () => {
    const nodes = [
      mockNode("a", "linear"),
      mockNode("b", "linear"),
      mockNode("c", "linear"),
      mockNode("d", "linear"),
    ];
    const edges = [
      mockEdge("a", "b"),
      mockEdge("b", "c"),
      mockEdge("c", "d"),
    ];

    const { doc1, doc2 } = roundTrip({ nodes, edges });

    expect(doc2.workflow.transitions).toEqual(doc1.workflow.transitions);
    expect(doc1.workflow.transitions).toEqual([
      { from: "a", to: "b" },
      { from: "b", to: "c" },
      { from: "c", to: "d" },
    ]);
  });
});

// ===========================================================================
// 5. Conditional transitions round-trip
// ===========================================================================

describe("Conditional transitions round-trip", () => {
  const outputConditions: CaseDef[] = [
    {
      case_id: "approved",
      condition_group: {
        combinator: "and",
        conditions: [{ eval_key: "result.status", operator: "eq", value: "ok" }],
      },
    },
    { case_id: "rejected",
      condition_group: {
        combinator: "and",
        conditions: [{ eval_key: "result.status", operator: "eq", value: "fail" }],
      },
    },
    { case_id: "default", default: true },
  ];

  it("conditional transitions survive compile -> parse -> compile", () => {
    const nodes = [
      mockNode("decider", "linear", {
        soulRef: "s1",
        outputConditions: outputConditions,
      }),
      mockNode("approve_step", "linear"),
      mockNode("reject_step", "linear"),
      mockNode("fallback", "linear"),
    ];
    const edges = [
      mockEdge("decider", "approve_step", "approved"),
      mockEdge("decider", "reject_step", "rejected"),
      mockEdge("decider", "fallback"),  // default handle
    ];

    const { doc1, doc2 } = roundTrip({ nodes, edges });

    expect(doc2.workflow.conditional_transitions).toEqual(
      doc1.workflow.conditional_transitions,
    );
  });

  it("mixed plain + conditional transitions survive round-trip", () => {
    const nodes = [
      mockNode("start", "linear", { soulRef: "s0" }),
      mockNode("decider", "gate", {
        soulRef: "gs",
        evalKey: "ok",
        outputConditions: [
          { case_id: "pass", condition_group: { combinator: "and", conditions: [{ eval_key: "score", operator: "gte", value: 5 }] } },
          { case_id: "fail", default: true },
        ],
      }),
      mockNode("pass_step", "linear"),
      mockNode("fail_step", "linear"),
    ];
    const edges = [
      mockEdge("start", "decider"),
      mockEdge("decider", "pass_step", "pass"),
      mockEdge("decider", "fail_step", "fail"),
    ];

    const { doc1, doc2 } = roundTrip({ nodes, edges });

    // Plain transitions
    expect(doc2.workflow.transitions).toEqual(doc1.workflow.transitions);
    // Conditional transitions
    expect(doc2.workflow.conditional_transitions).toEqual(
      doc1.workflow.conditional_transitions,
    );
  });

  it("conditional_transitions omitted when absent in both passes", () => {
    const nodes = [
      mockNode("a", "linear", { soulRef: "s1" }),
      mockNode("b", "linear"),
    ];
    const edges = [mockEdge("a", "b")];

    const { doc1, doc2 } = roundTrip({ nodes, edges });

    expect(doc1.workflow.conditional_transitions).toBeUndefined();
    expect(doc2.workflow.conditional_transitions).toBeUndefined();
  });
});

// ===========================================================================
// 6. Full workflow round-trip
// ===========================================================================

describe("Full workflow round-trip", () => {
  it("complex workflow with multiple types, edges, and config (RUN-574: no souls)", () => {
    const config: Record<string, unknown> = {
      max_concurrency: 8,
      timeout: 600,
    };

    const outputConds: CaseDef[] = [
      {
        case_id: "pass",
        condition_group: {
          combinator: "and",
          conditions: [{ eval_key: "quality", operator: "gte", value: 7 }],
        },
      },
      { case_id: "fail", default: true },
    ];

    const nodes = [
      mockNode("plan", "linear", { soulRef: "planner" }),
      mockNode("implement", "dispatch", { soulRefs: ["coder", "planner"] }),
      mockNode("review", "gate", {
        soulRef: "planner",
        evalKey: "quality",
        extractField: "score",
        outputConditions: outputConds,
      }),
      mockNode("pass_out", "file_writer", { outputPath: "./report.md", contentKey: "result" }),
      mockNode("fail_loop", "loop", { innerBlockRefs: ["implement"], maxRounds: 3, breakCondition: "result.ok == true" }),
    ];

    const edges = [
      mockEdge("plan", "implement"),
      mockEdge("implement", "review"),
      mockEdge("review", "pass_out", "pass"),
      mockEdge("review", "fail_loop", "fail"),
    ];

    const { doc1, doc2, yaml1, yaml2 } = roundTrip({
      nodes,
      edges,
      config,
      workflowName: "full-pipeline",
    });

    // Blocks
    expect(doc2.blocks).toEqual(doc1.blocks);

    // Souls are no longer emitted (RUN-574)
    expect(doc1).not.toHaveProperty("souls");
    expect(doc2).not.toHaveProperty("souls");

    // Config
    expect(doc2.config).toEqual(doc1.config);

    // Transitions
    expect(doc2.workflow.transitions).toEqual(doc1.workflow.transitions);

    // Conditional transitions
    expect(doc2.workflow.conditional_transitions).toEqual(
      doc1.workflow.conditional_transitions,
    );

    // Workflow name
    expect(doc2.workflow.name).toBe(doc1.workflow.name);

    // Entry point
    expect(doc2.workflow.entry).toBe(doc1.workflow.entry);

    // Version
    expect(doc2.version).toBe(doc1.version);

    // YAML string equivalence (strictest check)
    expect(yaml2).toBe(yaml1);
  });
});

// ===========================================================================
// 7. Edge cases
// ===========================================================================

describe("Edge cases", () => {
  it("empty workflow (no blocks) is a valid round-trip", () => {
    const { doc1, doc2, yaml1, yaml2 } = roundTrip({
      nodes: [],
      edges: [],
    });

    expect(doc2.blocks).toEqual(doc1.blocks);
    expect(yaml2).toBe(yaml1);
  });

  it("block with only type and no extra fields round-trips as minimal block", () => {
    const node = mockNode("minimal", "linear");
    const { doc1, doc2 } = roundTrip({ nodes: [node], edges: [] });

    expect(doc1.blocks["minimal"]).toEqual({ type: "linear" });
    expect(doc2.blocks["minimal"]).toEqual({ type: "linear" });
  });

  it("multiline code string preserved exactly through round-trip", () => {
    const multilineCode = `def main():
    data = {"key": "value"}
    for k, v in data.items():
        print(f"{k}: {v}")
    return data`;

    const node = mockNode("code_block", "code", {
      code: multilineCode,
      timeoutSeconds: 60,
      allowedImports: ["json", "os"],
    });

    const { doc1, doc2 } = roundTrip({ nodes: [node], edges: [] });

    expect(doc2.blocks["code_block"]).toEqual(doc1.blocks["code_block"]);
    // Specifically verify the code string
    expect((doc2.blocks["code_block"] as Record<string, unknown>).code).toBe(multilineCode);
  });

  it("workflow block with inputs and outputs round-trips", () => {
    const node = mockNode("sub", "workflow", {
      workflowRef: "sub.yaml",
      maxDepth: 3,
      workflowInputs: { query: "parent.user_query", context: "parent.ctx" },
      workflowOutputs: { summary: "child.result.summary" },
    });

    const { doc1, doc2 } = roundTrip({ nodes: [node], edges: [] });

    expect(doc2.blocks["sub"]).toEqual(doc1.blocks["sub"]);
  });

  it("block with universal fields (inputs, outputs, output_conditions) round-trips", () => {
    const node = mockNode("enriched", "linear", {
      soulRef: "soul1",
      inputs: { context: { from: "prev.result" } },
      outputs: { summary: "string" },
      outputConditions: [
        { case_id: "done", default: true },
      ],
    });

    const { doc1, doc2 } = roundTrip({ nodes: [node], edges: [] });

    expect(doc2.blocks["enriched"]).toEqual(doc1.blocks["enriched"]);
  });

  it("single node with no edges round-trips with correct entry point", () => {
    const node = mockNode("only_node", "linear", { soulRef: "s1" });
    const { doc1, doc2 } = roundTrip({ nodes: [node], edges: [] });

    expect(doc1.workflow.entry).toBe("only_node");
    expect(doc2.workflow.entry).toBe("only_node");
  });

  it("loop block with carryContext round-trips correctly", () => {
    const node = mockNode("loop1", "loop", {
      innerBlockRefs: ["step_a", "step_b"],
      maxRounds: 10,
      breakCondition: "result.converged == true",
      carryContext: {
        enabled: true,
        mode: "all",
        sourceBlocks: ["step_a", "step_b"],
        injectAs: "prior_results",
      },
    });

    const { doc1, doc2 } = roundTrip({ nodes: [node], edges: [] });

    // Verify the fields actually made it into the compiled document
    const block = doc1.blocks["loop1"] as Record<string, unknown>;
    expect(block).toHaveProperty("inner_block_refs");
    expect(block).toHaveProperty("max_rounds", 10);
    expect(block).toHaveProperty("break_condition");
    expect(block).toHaveProperty("carry_context");
    expect(doc2.blocks["loop1"]).toEqual(doc1.blocks["loop1"]);
  });

  it("block with retryConfig round-trips correctly", () => {
    const node = mockNode("resilient", "linear", {
      soulRef: "agent1",
      retryConfig: {
        maxAttempts: 3,
        backoff: "exponential",
        backoffBaseSeconds: 2,
        nonRetryableErrors: ["AuthError", "PermissionDenied"],
      },
    });

    const { doc1, doc2 } = roundTrip({ nodes: [node], edges: [] });

    // Verify retry_config actually made it into the compiled document
    const block = doc1.blocks["resilient"] as Record<string, unknown>;
    expect(block).toHaveProperty("retry_config");
    expect(doc2.blocks["resilient"]).toEqual(doc1.blocks["resilient"]);
  });

  it("loop block with retryConfig round-trips correctly", () => {
    const node = mockNode("retry_loop", "loop", {
      innerBlockRefs: ["flaky_step"],
      maxRounds: 5,
      retryConfig: {
        maxAttempts: 2,
        backoff: "fixed",
        backoffBaseSeconds: 5,
      },
    });

    const { doc1, doc2 } = roundTrip({ nodes: [node], edges: [] });

    // Verify both loop fields and retry_config made it
    const block = doc1.blocks["retry_loop"] as Record<string, unknown>;
    expect(block).toHaveProperty("inner_block_refs");
    expect(block).toHaveProperty("retry_config");
    expect(doc2.blocks["retry_loop"]).toEqual(doc1.blocks["retry_loop"]);
  });

  it("YAML string equality implies full lossless round-trip", () => {
    const nodes = [
      mockNode("a", "linear", { soulRef: "agent" }),
      mockNode("b", "dispatch", { soulRefs: ["agent", "agent"] }),
      mockNode("c", "code", { code: "x = 1", timeoutSeconds: 10, allowedImports: [] }),
    ];
    const edges = [mockEdge("a", "b"), mockEdge("b", "c")];

    const { yaml1, yaml2 } = roundTrip({
      nodes,
      edges,
      config: { debug: true },
      workflowName: "test-wf",
    });

    expect(yaml2).toBe(yaml1);
  });
});

// ===========================================================================
// 8. RUN-646 dispatch-only round-trip contract
// ===========================================================================

describe("Dispatch round-trip contract", () => {
  it("dispatch node round-trips with conditional transitions", () => {
    const nodes = [
      mockNode("dispatch_step", "dispatch", {
        soulRef: "classifier",
        outputConditions: [
          {
            case_id: "approved",
            condition_group: {
              combinator: "and",
              conditions: [{ eval_key: "result.status", operator: "eq", value: "approved" }],
            },
          },
          { case_id: "rejected", default: true },
        ],
      }),
      mockNode("approve", "linear"),
      mockNode("reject", "linear"),
    ];

    const edges = [
      mockEdge("dispatch_step", "approve", "approved"),
      mockEdge("dispatch_step", "reject"),
    ];

    const { doc1, doc2 } = roundTrip({ nodes, edges });
    expect((doc1.blocks["dispatch_step"] as Record<string, unknown>).type).toBe("dispatch");
    expect(doc2.blocks["dispatch_step"]).toEqual(doc1.blocks["dispatch_step"]);
  });
});
