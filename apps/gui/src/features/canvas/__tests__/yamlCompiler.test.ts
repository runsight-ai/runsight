/**
 * RED-TEAM tests for RUN-116: Compiler full per-type block field emission.
 *
 * These tests verify that `toCompiledBlock()` (via `compileGraphToWorkflowYaml`)
 * emits ALL valid fields per block type with snake_case keys, and excludes
 * runtime-only / cross-type fields.
 *
 * Expected to FAIL against the current implementation (which only emits `{ type }`).
 */

import { describe, it, expect } from "vitest";
import { compileGraphToWorkflowYaml } from "../yamlCompiler";
import type { StepNodeData, StepType, CaseDef, SoulDef } from "../../../types/schemas/canvas";
import type { Node, Edge } from "@xyflow/react";

// ---------------------------------------------------------------------------
// Helper: mock node factory
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

/** Compile a single node and return its block from the workflowDocument */
function compileOne(node: Node<StepNodeData>) {
  const result = compileGraphToWorkflowYaml({ nodes: [node], edges: [] });
  return {
    block: result.workflowDocument.blocks[node.id],
    yaml: result.yaml,
    doc: result.workflowDocument,
  };
}

// ---------------------------------------------------------------------------
// Shared fixtures
// ---------------------------------------------------------------------------

const sampleOutputConditions: CaseDef[] = [
  {
    case_id: "approved",
    condition_group: {
      combinator: "and",
      conditions: [{ eval_key: "result.status", operator: "eq", value: "ok" }],
    },
  },
  { case_id: "default", default: true },
];

// ===========================================================================
// 1. Per-type field emission
// ===========================================================================

describe("Per-type block field emission", () => {
  it("linear: emits soul_ref", () => {
    const { block } = compileOne(
      mockNode("b1", "linear", { soulRef: "planner_soul" }),
    );
    expect(block.type).toBe("linear");
    expect(block).toHaveProperty("soul_ref", "planner_soul");
  });

  it("dispatch: emits soul_refs array", () => {
    const { block } = compileOne(
      mockNode("b1", "dispatch", { soulRefs: ["s1", "s2", "s3"] }),
    );
    expect(block.type).toBe("dispatch");
    expect(block).toHaveProperty("soul_refs", ["s1", "s2", "s3"]);
  });

  it("synthesize: emits soul_ref and input_block_ids", () => {
    const { block } = compileOne(
      mockNode("b1", "synthesize", {
        soulRef: "synth_soul",
        inputBlockIds: ["a", "b"],
      }),
    );
    expect(block.type).toBe("synthesize");
    expect(block).toHaveProperty("soul_ref", "synth_soul");
    expect(block).toHaveProperty("input_block_ids", ["a", "b"]);
  });

  it("dispatch: emits soul_ref and does not emit condition_ref", () => {
    const { block } = compileOne(
      mockNode("b1", "dispatch", {
        soulRef: "dispatch_soul",
      }),
    );
    expect(block.type).toBe("dispatch");
    expect(block).toHaveProperty("soul_ref", "dispatch_soul");
    expect(block).not.toHaveProperty("condition_ref");
  });

  it("team_lead: emits soul_ref and failure_context_keys", () => {
    const { block } = compileOne(
      mockNode("b1", "team_lead", {
        soulRef: "lead_soul",
        failureContextKeys: ["error_trace", "last_output"],
      }),
    );
    expect(block.type).toBe("team_lead");
    expect(block).toHaveProperty("soul_ref", "lead_soul");
    expect(block).toHaveProperty("failure_context_keys", [
      "error_trace",
      "last_output",
    ]);
  });

  it("engineering_manager: emits soul_ref", () => {
    const { block } = compileOne(
      mockNode("b1", "engineering_manager", { soulRef: "em_soul" }),
    );
    expect(block.type).toBe("engineering_manager");
    expect(block).toHaveProperty("soul_ref", "em_soul");
  });

  it("gate: emits soul_ref, eval_key, extract_field", () => {
    const { block } = compileOne(
      mockNode("b1", "gate", {
        soulRef: "gate_soul",
        evalKey: "result.approved",
        extractField: "result.value",
      }),
    );
    expect(block.type).toBe("gate");
    expect(block).toHaveProperty("soul_ref", "gate_soul");
    expect(block).toHaveProperty("eval_key", "result.approved");
    expect(block).toHaveProperty("extract_field", "result.value");
  });

  it("file_writer: emits output_path and content_key", () => {
    const { block } = compileOne(
      mockNode("b1", "file_writer", {
        outputPath: "/tmp/report.md",
        contentKey: "result.markdown",
      }),
    );
    expect(block.type).toBe("file_writer");
    expect(block).toHaveProperty("output_path", "/tmp/report.md");
    expect(block).toHaveProperty("content_key", "result.markdown");
  });

  it("code: emits code, timeout_seconds, allowed_imports", () => {
    const { block } = compileOne(
      mockNode("b1", "code", {
        code: "print('hello')",
        timeoutSeconds: 60,
        allowedImports: ["json", "math"],
      }),
    );
    expect(block.type).toBe("code");
    expect(block).toHaveProperty("code", "print('hello')");
    expect(block).toHaveProperty("timeout_seconds", 60);
    expect(block).toHaveProperty("allowed_imports", ["json", "math"]);
  });

  it("loop: emits inner_block_refs, max_rounds, break_condition, carry_context", () => {
    const { block } = compileOne(
      mockNode("b1", "loop", {
        innerBlockRefs: ["step_a", "step_b"],
        maxRounds: 5,
        breakCondition: "result.converged == true",
        carryContext: {
          enabled: true,
          mode: "last",
          sourceBlocks: ["step_b"],
          injectAs: "previous_output",
        },
      }),
    );
    expect(block.type).toBe("loop");
    expect(block).toHaveProperty("inner_block_refs", ["step_a", "step_b"]);
    expect(block).toHaveProperty("max_rounds", 5);
    expect(block).toHaveProperty("break_condition", "result.converged == true");
    expect(block).toHaveProperty("carry_context");
    expect((block as Record<string, unknown>).carry_context).toEqual({
      enabled: true,
      mode: "last",
      source_blocks: ["step_b"],
      inject_as: "previous_output",
    });
  });

  it("loop: emits minimal loop with only inner_block_refs", () => {
    const { block } = compileOne(
      mockNode("b1", "loop", {
        innerBlockRefs: ["single_block"],
      }),
    );
    expect(block.type).toBe("loop");
    expect(block).toHaveProperty("inner_block_refs", ["single_block"]);
    expect(block).not.toHaveProperty("max_rounds");
    expect(block).not.toHaveProperty("break_condition");
    expect(block).not.toHaveProperty("carry_context");
  });

  it("workflow: emits workflow_ref and max_depth", () => {
    const { block } = compileOne(
      mockNode("b1", "workflow", {
        workflowRef: "sub_workflow.yaml",
        maxDepth: 5,
      }),
    );
    expect(block.type).toBe("workflow");
    expect(block).toHaveProperty("workflow_ref", "sub_workflow.yaml");
    expect(block).toHaveProperty("max_depth", 5);
  });

  it("workflow: emits inputs and outputs as string-valued maps", () => {
    const { block } = compileOne(
      mockNode("b1", "workflow", {
        workflowRef: "sub.yaml",
        workflowInputs: { query: "parent.user_query" },
        workflowOutputs: { summary: "child.result.summary" },
      }),
    );
    expect(block).toHaveProperty("inputs", { query: "parent.user_query" });
    expect(block).toHaveProperty("outputs", { summary: "child.result.summary" });
  });
});

// ===========================================================================
// 2. No cross-type leakage
// ===========================================================================

describe("Generic path emits all non-runtime fields", () => {
  it("linear node with extra fields emits them via generic path", () => {
    const { block } = compileOne(
      mockNode("b1", "linear", {
        soulRef: "soul1",
        iterations: 5,
      }),
    );
    // Generic path emits all non-runtime fields
    expect(block).toHaveProperty("soul_ref", "soul1");
    expect(block).toHaveProperty("iterations", 5);
  });

  it("code node with soulRef set emits soul_ref via generic path", () => {
    const { block } = compileOne(
      mockNode("b1", "code", {
        code: "x=1",
        soulRef: "some_soul",
      }),
    );
    // Generic path converts camelCase to snake_case for all fields
    expect(block).toHaveProperty("soul_ref", "some_soul");
  });

  it("gate node emits all fields via generic path", () => {
    const { block } = compileOne(
      mockNode("b1", "gate", {
        soulRef: "gate_soul",
        evalKey: "result.ok",
        iterations: 3,
        innerBlockRefs: ["x"],
      }),
    );
    expect(block).toHaveProperty("iterations", 3);
    expect(block).toHaveProperty("inner_block_refs");
  });

  it("dispatch node emits soul_ref alongside soul_refs via generic path", () => {
    const { block } = compileOne(
      mockNode("b1", "dispatch", {
        soulRefs: ["s1"],
        soulRef: "extra_soul",
      }),
    );
    expect(block).toHaveProperty("soul_ref", "extra_soul");
    expect(block).toHaveProperty("soul_refs");
  });

  it("code node emits all extra fields via generic path", () => {
    const { block } = compileOne(
      mockNode("b1", "code", {
        code: "x = 1",
        soulRef: "nope",
        iterations: 10,
      }),
    );
    expect(block).toHaveProperty("soul_ref", "nope");
    expect(block).toHaveProperty("iterations", 10);
  });

  it("file_writer node emits all fields via generic path", () => {
    const { block } = compileOne(
      mockNode("b1", "file_writer", {
        outputPath: "/out.txt",
        contentKey: "data",
        code: "some_code",
        soulRef: "extra",
      }),
    );
    expect(block).toHaveProperty("code", "some_code");
    expect(block).toHaveProperty("soul_ref", "extra");
  });
});

// ===========================================================================
// 3. Universal fields
// ===========================================================================

describe("Universal fields emitted on any block type", () => {
  it("output_conditions are emitted on a linear block", () => {
    const { block } = compileOne(
      mockNode("b1", "linear", {
        soulRef: "soul1",
        outputConditions: sampleOutputConditions,
      }),
    );
    expect(block).toHaveProperty("output_conditions");
    expect(block.output_conditions).toHaveLength(2);
    expect(block.output_conditions![0].case_id).toBe("approved");
  });

  it("inputs are emitted on a gate block", () => {
    const { block } = compileOne(
      mockNode("b1", "gate", {
        soulRef: "gs",
        evalKey: "ok",
        inputs: { context: { from: "step_a.result" } },
      }),
    );
    expect(block).toHaveProperty("inputs");
    expect(block.inputs).toEqual({ context: { from: "step_a.result" } });
  });

  it("outputs are emitted on a linear block", () => {
    const { block } = compileOne(
      mockNode("b1", "linear", {
        soulRef: "a",
        outputs: { winner: "string" },
      }),
    );
    expect(block).toHaveProperty("outputs");
    expect(block.outputs).toEqual({ winner: "string" });
  });

  it("output_conditions are emitted on a file_writer block", () => {
    const { block } = compileOne(
      mockNode("b1", "file_writer", {
        outputPath: "/out.txt",
        outputConditions: sampleOutputConditions,
      }),
    );
    expect(block).toHaveProperty("output_conditions");
  });

  it("retryConfig is emitted as retry_config on a linear block", () => {
    const { block } = compileOne(
      mockNode("b1", "linear", {
        soulRef: "soul1",
        retryConfig: {
          maxAttempts: 3,
          backoff: "exponential",
          backoffBaseSeconds: 2,
          nonRetryableErrors: ["AuthError"],
        },
      }),
    );
    expect(block).toHaveProperty("retry_config");
    expect((block as Record<string, unknown>).retry_config).toEqual({
      max_attempts: 3,
      backoff: "exponential",
      backoff_base_seconds: 2,
      non_retryable_errors: ["AuthError"],
    });
  });

  it("retryConfig is emitted as retry_config on a loop block", () => {
    const { block } = compileOne(
      mockNode("b1", "loop", {
        innerBlockRefs: ["step_a"],
        maxRounds: 3,
        retryConfig: {
          maxAttempts: 2,
          backoff: "fixed",
          backoffBaseSeconds: 5,
        },
      }),
    );
    expect(block).toHaveProperty("retry_config");
    expect((block as Record<string, unknown>).retry_config).toEqual({
      max_attempts: 2,
      backoff: "fixed",
      backoff_base_seconds: 5,
    });
  });

  it("retryConfig is emitted as retry_config on a code block", () => {
    const { block } = compileOne(
      mockNode("b1", "code", {
        code: "run()",
        retryConfig: {
          maxAttempts: 5,
          backoff: "exponential",
          backoffBaseSeconds: 1,
        },
      }),
    );
    expect(block).toHaveProperty("retry_config");
  });
});

// ===========================================================================
// 4. Undefined/null field omission
// ===========================================================================

describe("Undefined and null field omission", () => {
  it("undefined optional fields are omitted from compiled output", () => {
    const { block } = compileOne(
      mockNode("b1", "gate", {
        soulRef: "gs",
        evalKey: "ok",
        // extractField is undefined
      }),
    );
    expect(block).toHaveProperty("soul_ref");
    expect(block).toHaveProperty("eval_key");
    expect(block).not.toHaveProperty("extract_field");
  });

  it("null fields are omitted from compiled output", () => {
    const { block } = compileOne(
      mockNode("b1", "loop", {
        innerBlockRefs: ["target"],
        maxRounds: undefined,
        breakCondition: undefined,
        carryContext: undefined,
      }),
    );
    expect(block).toHaveProperty("inner_block_refs", ["target"]);
    expect(block).not.toHaveProperty("max_rounds");
    expect(block).not.toHaveProperty("break_condition");
    expect(block).not.toHaveProperty("carry_context");
  });

  it("empty arrays are still emitted (they are valid values)", () => {
    const { block } = compileOne(
      mockNode("b1", "code", {
        code: "pass",
        allowedImports: [],
      }),
    );
    expect(block).toHaveProperty("allowed_imports", []);
  });

  it("team_lead with undefined failureContextKeys omits the field", () => {
    const { block } = compileOne(
      mockNode("b1", "team_lead", {
        soulRef: "tl",
        // failureContextKeys not set
      }),
    );
    expect(block).toHaveProperty("soul_ref", "tl");
    expect(block).not.toHaveProperty("failure_context_keys");
  });
});

// ===========================================================================
// 5. Runtime fields excluded
// ===========================================================================

describe("Runtime fields excluded from compiled output", () => {
  const runtimeFields = ["status", "cost", "executionCost", "name", "stepId"];

  for (const field of runtimeFields) {
    it(`${field} is NOT present in compiled block`, () => {
      const { block } = compileOne(
        mockNode("b1", "linear", {
          soulRef: "soul1",
          cost: 0.05,
          executionCost: 0.12,
        }),
      );
      // Check both camelCase and snake_case forms
      expect(block).not.toHaveProperty(field);
      const snakeCase = field.replace(
        /[A-Z]/g,
        (m) => `_${m.toLowerCase()}`,
      );
      if (snakeCase !== field) {
        expect(block).not.toHaveProperty(snakeCase);
      }
    });
  }

  it("runtime fields are absent from YAML string output", () => {
    const { yaml } = compileOne(
      mockNode("b1", "linear", {
        soulRef: "soul1",
        cost: 0.05,
        executionCost: 0.12,
      }),
    );
    expect(yaml).not.toContain("status:");
    expect(yaml).not.toContain("cost:");
    expect(yaml).not.toContain("execution_cost:");
    expect(yaml).not.toContain("executionCost:");
    expect(yaml).not.toContain("stepId:");
    expect(yaml).not.toContain("step_id:");
    // name is used in workflow.name, but should not appear inside a block
    expect(yaml).toContain("soul_ref: soul1");
  });
});

// ===========================================================================
// 6. Empty / minimal node
// ===========================================================================

describe("Empty / minimal node compilation", () => {
  it("file_writer with no extra fields emits only { type: 'file_writer' }", () => {
    const { block } = compileOne(mockNode("b1", "file_writer"));
    expect(block).toEqual({ type: "file_writer" });
  });

  it("linear with only soulRef emits { type, soul_ref } and nothing else", () => {
    const { block } = compileOne(
      mockNode("b1", "linear", { soulRef: "s1" }),
    );
    expect(block).toEqual({ type: "linear", soul_ref: "s1" });
  });
});

// ===========================================================================
// 7. CompiledWorkflow uses BlockDef (not { type: string })
// ===========================================================================

describe("CompiledWorkflow blocks use full BlockDef shape", () => {
  it("blocks record contains fully typed BlockDef objects", () => {
    const node = mockNode("b1", "gate", {
      soulRef: "gatekeeper",
      evalKey: "quality",
      extractField: "score",
    });
    const { doc } = compileOne(node);
    const block = doc.blocks["b1"];

    // Should have more than just `type`
    expect(Object.keys(block).length).toBeGreaterThan(1);
    expect(block).toHaveProperty("soul_ref");
    expect(block).toHaveProperty("eval_key");
    expect(block).toHaveProperty("extract_field");
  });

  it("YAML output contains snake_case field keys within blocks", () => {
    const node = mockNode("b1", "gate", {
      soulRef: "gatekeeper",
      evalKey: "quality",
      extractField: "score",
    });
    const { yaml } = compileOne(node);

    // snake_case keys in YAML
    expect(yaml).toContain("soul_ref:");
    expect(yaml).toContain("eval_key:");
    expect(yaml).toContain("extract_field:");

    // camelCase should NOT appear
    expect(yaml).not.toContain("soulRef:");
    expect(yaml).not.toContain("evalKey:");
  });

  it("multiple nodes each emit their own typed fields", () => {
    const nodes = [
      mockNode("linear1", "linear", { soulRef: "s1" }),
      mockNode("code1", "code", { code: "x=1", timeoutSeconds: 30 }),
      mockNode("gate1", "gate", {
        soulRef: "gs",
        evalKey: "ok",
        extractField: "val",
      }),
    ];
    const result = compileGraphToWorkflowYaml({ nodes, edges: [] });
    const blocks = result.workflowDocument.blocks;

    expect(blocks["linear1"]).toEqual({ type: "linear", soul_ref: "s1" });
    expect(blocks["code1"]).toEqual({
      type: "code",
      code: "x=1",
      timeout_seconds: 30,
    });
    expect(blocks["gate1"]).toEqual({
      type: "gate",
      soul_ref: "gs",
      eval_key: "ok",
      extract_field: "val",
    });
  });
});

// ===========================================================================
// 8. RUN-646 dispatch-only editor compile contract
// ===========================================================================

describe("RUN-646 dispatch-only compile contract", () => {
  it("dispatch block does not emit legacy condition_ref", () => {
    const { block } = compileOne(
      mockNode("b1", "dispatch", {
        soulRef: "branch_soul",
        conditionRef: "legacy_condition",
      }),
    );
    expect(block.type).toBe("dispatch");
    expect(block).not.toHaveProperty("condition_ref");
  });

  it("legacy fanout editor block type is rejected at compile time", () => {
    expect(() =>
      compileOne(mockNode("b1", "fanout", { soulRefs: ["s1", "s2"] })),
    ).toThrow(/fanout|dispatch|unsupported/i);
  });

  it("legacy router editor block type is rejected at compile time", () => {
    expect(() =>
      compileOne(
        mockNode("b1", "router", {
          soulRef: "router_soul",
          conditionRef: "route_cond",
        }),
      ),
    ).toThrow(/router|dispatch|unsupported/i);
  });
});

// ===========================================================================
// 8. YAML string fidelity (snake_case keys for all types)
// ===========================================================================

describe("YAML string output uses snake_case keys", () => {
  it("file_writer fields use snake_case in YAML", () => {
    const { yaml } = compileOne(
      mockNode("b1", "file_writer", {
        outputPath: "/tmp/out.txt",
        contentKey: "result.text",
      }),
    );
    expect(yaml).toContain("output_path:");
    expect(yaml).toContain("content_key:");
    expect(yaml).not.toContain("outputPath:");
    expect(yaml).not.toContain("contentKey:");
  });

  it("loop fields use snake_case in YAML", () => {
    const { yaml } = compileOne(
      mockNode("b1", "loop", {
        innerBlockRefs: ["block_a", "block_b"],
        maxRounds: 10,
        breakCondition: "result.done == true",
      }),
    );
    expect(yaml).toContain("inner_block_refs:");
    expect(yaml).toContain("max_rounds:");
    expect(yaml).toContain("break_condition:");
    expect(yaml).not.toContain("innerBlockRefs:");
    expect(yaml).not.toContain("maxRounds:");
    expect(yaml).not.toContain("breakCondition:");
  });

  it("code fields use snake_case in YAML", () => {
    const { yaml } = compileOne(
      mockNode("b1", "code", {
        code: "x=1",
        timeoutSeconds: 45,
        allowedImports: ["os"],
      }),
    );
    expect(yaml).toContain("timeout_seconds:");
    expect(yaml).toContain("allowed_imports:");
    expect(yaml).not.toContain("timeoutSeconds:");
    expect(yaml).not.toContain("allowedImports:");
  });

  it("synthesize fields use snake_case in YAML", () => {
    const { yaml } = compileOne(
      mockNode("b1", "synthesize", {
        soulRef: "synth",
        inputBlockIds: ["a", "b"],
      }),
    );
    expect(yaml).toContain("soul_ref:");
    expect(yaml).toContain("input_block_ids:");
    expect(yaml).not.toContain("soulRef:");
    expect(yaml).not.toContain("inputBlockIds:");
  });

  it("output_conditions uses snake_case in YAML", () => {
    const { yaml } = compileOne(
      mockNode("b1", "linear", {
        soulRef: "s1",
        outputConditions: sampleOutputConditions,
      }),
    );
    expect(yaml).toContain("output_conditions:");
    expect(yaml).not.toContain("outputConditions:");
  });

  it("retryConfig fields use snake_case in YAML", () => {
    const { yaml } = compileOne(
      mockNode("b1", "linear", {
        soulRef: "s1",
        retryConfig: {
          maxAttempts: 3,
          backoff: "exponential",
          backoffBaseSeconds: 2,
          nonRetryableErrors: ["TimeoutError"],
        },
      }),
    );
    expect(yaml).toContain("retry_config:");
    expect(yaml).toContain("max_attempts:");
    expect(yaml).toContain("backoff_base_seconds:");
    expect(yaml).toContain("non_retryable_errors:");
    expect(yaml).not.toContain("retryConfig:");
    expect(yaml).not.toContain("maxAttempts:");
    expect(yaml).not.toContain("backoffBaseSeconds:");
    expect(yaml).not.toContain("nonRetryableErrors:");
  });
});

// ===========================================================================
// 9. Souls and config top-level sections (RUN-117)
// ===========================================================================

describe("Souls and config top-level sections", () => {
  const sampleSouls: Record<string, SoulDef> = {
    planner: {
      id: "planner",
      role: "planner",
      system_prompt: "You are a planning agent.",
    },
  };

  const sampleConfig: Record<string, unknown> = {
    max_concurrency: 4,
    timeout: 300,
  };

  it("souls are NOT included in compiled output even when provided (RUN-574)", () => {
    const result = compileGraphToWorkflowYaml({
      nodes: [mockNode("b1", "linear", { soulRef: "planner" })],
      edges: [],
      souls: sampleSouls,
    });
    expect(result.workflowDocument).not.toHaveProperty("souls");
  });

  it("config is included in compiled output when provided", () => {
    const result = compileGraphToWorkflowYaml({
      nodes: [mockNode("b1", "linear", { soulRef: "s1" })],
      edges: [],
      config: sampleConfig,
    });
    expect(result.workflowDocument.config).toEqual(sampleConfig);
  });

  it("souls do NOT appear in YAML string output even when provided (RUN-574)", () => {
    const result = compileGraphToWorkflowYaml({
      nodes: [mockNode("b1", "linear", { soulRef: "planner" })],
      edges: [],
      souls: sampleSouls,
    });
    expect(result.yaml).not.toMatch(/^souls:/m);
  });

  it("config appears in YAML string output", () => {
    const result = compileGraphToWorkflowYaml({
      nodes: [mockNode("b1", "linear", { soulRef: "s1" })],
      edges: [],
      config: sampleConfig,
    });
    expect(result.yaml).toContain("config:");
    expect(result.yaml).toContain("max_concurrency: 4");
    expect(result.yaml).toContain("timeout: 300");
  });

  it("empty souls object is omitted (RUN-574)", () => {
    const result = compileGraphToWorkflowYaml({
      nodes: [mockNode("b1", "linear")],
      edges: [],
      souls: {},
    });
    expect(result.workflowDocument).not.toHaveProperty("souls");
    expect(result.yaml).not.toContain("souls:");
  });

  it("empty config object is omitted", () => {
    const result = compileGraphToWorkflowYaml({
      nodes: [mockNode("b1", "linear")],
      edges: [],
      config: {},
    });
    expect(result.workflowDocument.config).toBeUndefined();
    expect(result.yaml).not.toContain("config:");
  });

  it("undefined souls/config are omitted (RUN-574)", () => {
    const result = compileGraphToWorkflowYaml({
      nodes: [mockNode("b1", "linear")],
      edges: [],
    });
    expect(result.workflowDocument).not.toHaveProperty("souls");
    expect(result.workflowDocument.config).toBeUndefined();
    expect(result.yaml).not.toContain("souls:");
    expect(result.yaml).not.toContain("config:");
  });

  it("soul fields are NOT serialized to top-level souls section (RUN-574)", () => {
    const fullSoul: SoulDef = {
      id: "coder",
      role: "engineer",
      system_prompt: "You write code.",
      tools: [{ name: "file_read", config: { root: "/src" } }],
      model_name: "claude-3-opus",
    };
    const result = compileGraphToWorkflowYaml({
      nodes: [mockNode("b1", "linear", { soulRef: "coder" })],
      edges: [],
      souls: { coder: fullSoul },
    });
    // After RUN-574, souls are never emitted in the compiled output
    expect(result.workflowDocument).not.toHaveProperty("souls");
    expect(result.yaml).not.toMatch(/^souls:/m);
    // But soul_ref on blocks should still work
    expect(result.workflowDocument.blocks["b1"]).toHaveProperty("soul_ref", "coder");
  });

  it("config with nested objects serializes correctly", () => {
    const nestedConfig: Record<string, unknown> = {
      retry_policy: {
        max_retries: 3,
        backoff: { type: "exponential", base_ms: 100 },
      },
      logging: { level: "debug" },
    };
    const result = compileGraphToWorkflowYaml({
      nodes: [mockNode("b1", "linear")],
      edges: [],
      config: nestedConfig,
    });
    expect(result.workflowDocument.config).toEqual(nestedConfig);
    expect(result.yaml).toContain("retry_policy:");
    expect(result.yaml).toContain("max_retries: 3");
    expect(result.yaml).toContain("type: exponential");
    expect(result.yaml).toContain("base_ms: 100");
    expect(result.yaml).toContain("level: debug");
  });
});

// ===========================================================================
// 10. Conditional transitions compilation (RUN-118)
// ===========================================================================

/**
 * RED-TEAM tests for RUN-118: conditional_transitions emission.
 *
 * Edges from nodes WITH output_conditions should go into
 * `workflow.conditional_transitions`; edges from nodes WITHOUT
 * output_conditions stay in `workflow.transitions`.
 *
 * Expected to FAIL against the current implementation which puts ALL
 * edges into `workflow.transitions` regardless of output_conditions.
 */
describe("Conditional transitions compilation", () => {
  // ── helpers ──────────────────────────────────────────────────────────────

  function mockNodeWithConditions(
    id: string,
    stepType: StepType,
    cases: string[],
  ): Node<StepNodeData> {
    return mockNode(id, stepType, {
      soulRef: "test-soul",
      outputConditions: cases.map((c) =>
        c === "default"
          ? { case_id: c, default: true }
          : {
              case_id: c,
              condition_group: {
                combinator: "and",
                conditions: [
                  { eval_key: "score", operator: "gte", value: 5 },
                ],
              },
            },
      ),
    });
  }

  function mockEdge(
    source: string,
    target: string,
    sourceHandle?: string,
  ): Edge {
    return {
      id: `${source}->${target}`,
      source,
      target,
      sourceHandle: sourceHandle ?? null,
      targetHandle: null,
    };
  }

  // ── tests ────────────────────────────────────────────────────────────────

  it("edges from node with output_conditions go into conditional_transitions, not transitions", () => {
    const nodes = [
      mockNodeWithConditions("router", "linear", ["approved", "rejected", "default"]),
      mockNode("approve_step", "linear", { soulRef: "s1" }),
      mockNode("reject_step", "linear", { soulRef: "s2" }),
    ];
    const edges = [
      mockEdge("router", "approve_step", "approved"),
      mockEdge("router", "reject_step", "rejected"),
    ];
    const result = compileGraphToWorkflowYaml({ nodes, edges });
    const wf = result.workflowDocument.workflow as Record<string, unknown>;

    // Should appear in conditional_transitions
    expect(wf.conditional_transitions).toBeDefined();
    expect((wf.conditional_transitions as unknown[]).length).toBeGreaterThanOrEqual(1);

    // Should NOT appear in plain transitions
    const transitions = wf.transitions as Array<{ from: string; to: string }>;
    const plainFromRouter = transitions.filter((t) => t.from === "router");
    expect(plainFromRouter).toHaveLength(0);
  });

  it("edges from node WITHOUT output_conditions stay in transitions", () => {
    const nodes = [
      mockNode("step_a", "linear", { soulRef: "s1" }),
      mockNode("step_b", "linear", { soulRef: "s2" }),
    ];
    const edges = [mockEdge("step_a", "step_b")];
    const result = compileGraphToWorkflowYaml({ nodes, edges });
    const wf = result.workflowDocument.workflow as Record<string, unknown>;

    expect(wf.transitions).toEqual([{ from: "step_a", to: "step_b" }]);
    expect(wf.conditional_transitions).toBeUndefined();
  });

  it("mixed: some edges conditional, some plain — correctly separated", () => {
    const nodes = [
      mockNode("plain_start", "linear", { soulRef: "s0" }),
      mockNodeWithConditions("decision", "gate", ["pass", "fail", "default"]),
      mockNode("pass_step", "linear", { soulRef: "s1" }),
      mockNode("fail_step", "linear", { soulRef: "s2" }),
      mockNode("fallback", "linear"),
    ];
    const edges = [
      mockEdge("plain_start", "decision"),          // plain
      mockEdge("decision", "pass_step", "pass"),    // conditional
      mockEdge("decision", "fail_step", "fail"),    // conditional
      mockEdge("decision", "fallback"),              // default (no sourceHandle)
    ];
    const result = compileGraphToWorkflowYaml({ nodes, edges });
    const wf = result.workflowDocument.workflow as Record<string, unknown>;

    // Plain transition
    expect(wf.transitions).toEqual([{ from: "plain_start", to: "decision" }]);

    // Conditional transitions
    expect(wf.conditional_transitions).toBeDefined();
    const ctArray = wf.conditional_transitions as Record<string, string>[];
    expect(ctArray.length).toBe(1);
    const ct = ctArray[0];
    expect(ct.from).toBe("decision");
    expect(ct["pass"]).toBe("pass_step");
    expect(ct["fail"]).toBe("fail_step");
    expect(ct["default"]).toBe("fallback");
  });

  it("sourceHandle maps to decision key in conditional_transitions", () => {
    const nodes = [
      mockNodeWithConditions("decider", "linear", ["yes", "no"]),
      mockNode("yes_target", "linear"),
      mockNode("no_target", "linear"),
    ];
    const edges = [
      mockEdge("decider", "yes_target", "yes"),
      mockEdge("decider", "no_target", "no"),
    ];
    const result = compileGraphToWorkflowYaml({ nodes, edges });
    const wf = result.workflowDocument.workflow as Record<string, unknown>;
    const ct = wf.conditional_transitions as Record<string, string>[];

    expect(ct).toBeDefined();
    expect(ct.length).toBe(1);
    expect(ct[0].from).toBe("decider");
    expect(ct[0]["yes"]).toBe("yes_target");
    expect(ct[0]["no"]).toBe("no_target");
  });

  it("edge without sourceHandle from conditioned node maps to default", () => {
    const nodes = [
      mockNodeWithConditions("decider", "linear", ["option_a", "default"]),
      mockNode("a_target", "linear"),
      mockNode("fallback_target", "linear"),
    ];
    const edges = [
      mockEdge("decider", "a_target", "option_a"),
      mockEdge("decider", "fallback_target"),          // no sourceHandle → default
    ];
    const result = compileGraphToWorkflowYaml({ nodes, edges });
    const wf = result.workflowDocument.workflow as Record<string, unknown>;
    const ct = wf.conditional_transitions as Record<string, string>[];

    expect(ct).toBeDefined();
    expect(ct[0]["default"]).toBe("fallback_target");
    expect(ct[0]["option_a"]).toBe("a_target");
  });

  it("multiple conditional edges from same source grouped into one entry", () => {
    const nodes = [
      mockNodeWithConditions("src", "linear", ["a", "b", "c", "default"]),
      mockNode("t_a", "linear"),
      mockNode("t_b", "linear"),
      mockNode("t_c", "linear"),
      mockNode("t_default", "linear"),
    ];
    const edges = [
      mockEdge("src", "t_a", "a"),
      mockEdge("src", "t_b", "b"),
      mockEdge("src", "t_c", "c"),
      mockEdge("src", "t_default"),           // default
    ];
    const result = compileGraphToWorkflowYaml({ nodes, edges });
    const wf = result.workflowDocument.workflow as Record<string, unknown>;
    const ct = wf.conditional_transitions as Record<string, string>[];

    // All four edges should be grouped into a single entry
    expect(ct).toHaveLength(1);
    expect(ct[0].from).toBe("src");
    expect(ct[0]["a"]).toBe("t_a");
    expect(ct[0]["b"]).toBe("t_b");
    expect(ct[0]["c"]).toBe("t_c");
    expect(ct[0]["default"]).toBe("t_default");
  });

  it("conditional_transitions section omitted when no conditional edges exist", () => {
    const nodes = [
      mockNode("s1", "linear", { soulRef: "soul1" }),
      mockNode("s2", "linear", { soulRef: "soul2" }),
    ];
    const edges = [mockEdge("s1", "s2")];
    const result = compileGraphToWorkflowYaml({ nodes, edges });
    const wf = result.workflowDocument.workflow as Record<string, unknown>;

    expect(wf.conditional_transitions).toBeUndefined();
    expect(result.yaml).not.toContain("conditional_transitions");
  });

  it("output_conditions on block still emitted in blocks section", () => {
    const nodes = [
      mockNodeWithConditions("decider", "linear", ["yes", "no", "default"]),
      mockNode("target", "linear"),
    ];
    const edges = [mockEdge("decider", "target", "yes")];
    const result = compileGraphToWorkflowYaml({ nodes, edges });

    // Block should still have output_conditions
    const block = result.workflowDocument.blocks["decider"];
    expect(block.output_conditions).toBeDefined();
    expect(block.output_conditions).toHaveLength(3);
    expect(block.output_conditions!.map((c) => c.case_id)).toEqual(["yes", "no", "default"]);
  });

  it("node with output_conditions but no outgoing edges — no conditional_transition entry", () => {
    const nodes = [
      mockNodeWithConditions("orphan", "linear", ["a", "b", "default"]),
    ];
    const result = compileGraphToWorkflowYaml({ nodes, edges: [] });
    const wf = result.workflowDocument.workflow as Record<string, unknown>;

    // No edges → no conditional_transitions section
    expect(wf.conditional_transitions).toBeUndefined();
  });

  it("YAML string contains conditional_transitions section", () => {
    const nodes = [
      mockNodeWithConditions("router_block", "linear", ["approved", "rejected", "default"]),
      mockNode("approve_block", "linear"),
      mockNode("reject_block", "linear"),
      mockNode("fallback_block", "linear"),
    ];
    const edges = [
      mockEdge("router_block", "approve_block", "approved"),
      mockEdge("router_block", "reject_block", "rejected"),
      mockEdge("router_block", "fallback_block"),   // default
    ];
    const result = compileGraphToWorkflowYaml({ nodes, edges });

    expect(result.yaml).toContain("conditional_transitions:");
    expect(result.yaml).toContain("from: router_block");
    expect(result.yaml).toContain("approved: approve_block");
    expect(result.yaml).toContain("rejected: reject_block");
    expect(result.yaml).toContain("default: fallback_block");
  });
});
