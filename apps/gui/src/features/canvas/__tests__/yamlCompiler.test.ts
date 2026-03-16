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
import type { Node } from "@xyflow/react";

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

  it("fanout: emits soul_refs array", () => {
    const { block } = compileOne(
      mockNode("b1", "fanout", { soulRefs: ["s1", "s2", "s3"] }),
    );
    expect(block.type).toBe("fanout");
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

  it("debate: emits soul_a_ref, soul_b_ref, iterations", () => {
    const { block } = compileOne(
      mockNode("b1", "debate", {
        soulARef: "alice",
        soulBRef: "bob",
        iterations: 5,
      }),
    );
    expect(block.type).toBe("debate");
    expect(block).toHaveProperty("soul_a_ref", "alice");
    expect(block).toHaveProperty("soul_b_ref", "bob");
    expect(block).toHaveProperty("iterations", 5);
  });

  it("message_bus: emits soul_refs and iterations", () => {
    const { block } = compileOne(
      mockNode("b1", "message_bus", {
        soulRefs: ["s1", "s2"],
        iterations: 3,
      }),
    );
    expect(block.type).toBe("message_bus");
    expect(block).toHaveProperty("soul_refs", ["s1", "s2"]);
    expect(block).toHaveProperty("iterations", 3);
  });

  it("router: emits soul_ref and condition_ref", () => {
    const { block } = compileOne(
      mockNode("b1", "router", {
        soulRef: "router_soul",
        conditionRef: "cond_1",
      }),
    );
    expect(block.type).toBe("router");
    expect(block).toHaveProperty("soul_ref", "router_soul");
    expect(block).toHaveProperty("condition_ref", "cond_1");
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

  it("placeholder: emits description", () => {
    const { block } = compileOne(
      mockNode("b1", "placeholder", { description: "TODO: implement" }),
    );
    expect(block.type).toBe("placeholder");
    expect(block).toHaveProperty("description", "TODO: implement");
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

  it("retry: emits inner_block_ref, max_retries, provide_error_context", () => {
    const { block } = compileOne(
      mockNode("b1", "retry", {
        innerBlockRef: "flaky_block",
        maxRetries: 3,
        provideErrorContext: true,
      }),
    );
    expect(block.type).toBe("retry");
    expect(block).toHaveProperty("inner_block_ref", "flaky_block");
    expect(block).toHaveProperty("max_retries", 3);
    expect(block).toHaveProperty("provide_error_context", true);
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

describe("No cross-type field leakage", () => {
  it("linear node with iterations set does NOT emit iterations", () => {
    const { block } = compileOne(
      mockNode("b1", "linear", {
        soulRef: "soul1",
        iterations: 5, // iterations belongs to debate/message_bus
      }),
    );
    expect(block).not.toHaveProperty("iterations");
  });

  it("placeholder node with soulRef set does NOT emit soul_ref", () => {
    const { block } = compileOne(
      mockNode("b1", "placeholder", {
        soulRef: "some_soul", // soulRef does not belong to placeholder
      }),
    );
    expect(block).not.toHaveProperty("soul_ref");
  });

  it("gate node does NOT emit iterations or inner_block_ref", () => {
    const { block } = compileOne(
      mockNode("b1", "gate", {
        soulRef: "gate_soul",
        evalKey: "result.ok",
        iterations: 3,       // belongs to debate/message_bus
        innerBlockRef: "x",  // belongs to retry
      }),
    );
    expect(block).not.toHaveProperty("iterations");
    expect(block).not.toHaveProperty("inner_block_ref");
  });

  it("fanout node does NOT emit soul_ref (singular)", () => {
    const { block } = compileOne(
      mockNode("b1", "fanout", {
        soulRefs: ["s1"],
        soulRef: "should_not_appear",
      }),
    );
    expect(block).not.toHaveProperty("soul_ref");
  });

  it("code node does NOT emit soul_ref or iterations", () => {
    const { block } = compileOne(
      mockNode("b1", "code", {
        code: "x = 1",
        soulRef: "nope",
        iterations: 10,
      }),
    );
    expect(block).not.toHaveProperty("soul_ref");
    expect(block).not.toHaveProperty("iterations");
  });

  it("file_writer node does NOT emit code or soul_ref", () => {
    const { block } = compileOne(
      mockNode("b1", "file_writer", {
        outputPath: "/out.txt",
        contentKey: "data",
        code: "should_not_appear",
        soulRef: "also_no",
      }),
    );
    expect(block).not.toHaveProperty("code");
    expect(block).not.toHaveProperty("soul_ref");
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

  it("outputs are emitted on a debate block", () => {
    const { block } = compileOne(
      mockNode("b1", "debate", {
        soulARef: "a",
        soulBRef: "b",
        iterations: 2,
        outputs: { winner: "string" },
      }),
    );
    expect(block).toHaveProperty("outputs");
    expect(block.outputs).toEqual({ winner: "string" });
  });

  it("output_conditions are emitted on a placeholder block", () => {
    const { block } = compileOne(
      mockNode("b1", "placeholder", {
        outputConditions: sampleOutputConditions,
      }),
    );
    expect(block).toHaveProperty("output_conditions");
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
      mockNode("b1", "retry", {
        innerBlockRef: "target",
        maxRetries: undefined,
        provideErrorContext: undefined,
      }),
    );
    expect(block).toHaveProperty("inner_block_ref", "target");
    expect(block).not.toHaveProperty("max_retries");
    expect(block).not.toHaveProperty("provide_error_context");
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
  it("placeholder with no extra fields emits only { type: 'placeholder' }", () => {
    const { block } = compileOne(mockNode("b1", "placeholder"));
    expect(block).toEqual({ type: "placeholder" });
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
    const node = mockNode("b1", "debate", {
      soulARef: "alice",
      soulBRef: "bob",
      iterations: 3,
    });
    const { doc } = compileOne(node);
    const block = doc.blocks["b1"];

    // Should have more than just `type`
    expect(Object.keys(block).length).toBeGreaterThan(1);
    expect(block).toHaveProperty("soul_a_ref");
    expect(block).toHaveProperty("soul_b_ref");
    expect(block).toHaveProperty("iterations");
  });

  it("YAML output contains snake_case field keys within blocks", () => {
    const node = mockNode("b1", "debate", {
      soulARef: "alice",
      soulBRef: "bob",
      iterations: 3,
    });
    const { yaml } = compileOne(node);

    // snake_case keys in YAML
    expect(yaml).toContain("soul_a_ref:");
    expect(yaml).toContain("soul_b_ref:");
    expect(yaml).toContain("iterations:");

    // camelCase should NOT appear
    expect(yaml).not.toContain("soulARef:");
    expect(yaml).not.toContain("soulBRef:");
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

  it("retry fields use snake_case in YAML", () => {
    const { yaml } = compileOne(
      mockNode("b1", "retry", {
        innerBlockRef: "target",
        maxRetries: 3,
        provideErrorContext: true,
      }),
    );
    expect(yaml).toContain("inner_block_ref:");
    expect(yaml).toContain("max_retries:");
    expect(yaml).toContain("provide_error_context:");
    expect(yaml).not.toContain("innerBlockRef:");
    expect(yaml).not.toContain("maxRetries:");
    expect(yaml).not.toContain("provideErrorContext:");
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

  it("souls are included in compiled output when provided", () => {
    const result = compileGraphToWorkflowYaml({
      nodes: [mockNode("b1", "linear", { soulRef: "planner" })],
      edges: [],
      souls: sampleSouls,
    });
    expect(result.workflowDocument.souls).toEqual(sampleSouls);
  });

  it("config is included in compiled output when provided", () => {
    const result = compileGraphToWorkflowYaml({
      nodes: [mockNode("b1", "linear", { soulRef: "s1" })],
      edges: [],
      config: sampleConfig,
    });
    expect(result.workflowDocument.config).toEqual(sampleConfig);
  });

  it("souls appear in YAML string output", () => {
    const result = compileGraphToWorkflowYaml({
      nodes: [mockNode("b1", "linear", { soulRef: "planner" })],
      edges: [],
      souls: sampleSouls,
    });
    expect(result.yaml).toContain("souls:");
    expect(result.yaml).toContain("planner:");
    expect(result.yaml).toContain("system_prompt: You are a planning agent.");
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

  it("empty souls object is omitted", () => {
    const result = compileGraphToWorkflowYaml({
      nodes: [mockNode("b1", "placeholder")],
      edges: [],
      souls: {},
    });
    expect(result.workflowDocument.souls).toBeUndefined();
    expect(result.yaml).not.toContain("souls:");
  });

  it("empty config object is omitted", () => {
    const result = compileGraphToWorkflowYaml({
      nodes: [mockNode("b1", "placeholder")],
      edges: [],
      config: {},
    });
    expect(result.workflowDocument.config).toBeUndefined();
    expect(result.yaml).not.toContain("config:");
  });

  it("undefined souls/config are omitted", () => {
    const result = compileGraphToWorkflowYaml({
      nodes: [mockNode("b1", "placeholder")],
      edges: [],
    });
    expect(result.workflowDocument.souls).toBeUndefined();
    expect(result.workflowDocument.config).toBeUndefined();
    expect(result.yaml).not.toContain("souls:");
    expect(result.yaml).not.toContain("config:");
  });

  it("soul with all fields is serialized correctly", () => {
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
    const compiled = result.workflowDocument.souls!["coder"];
    expect(compiled.id).toBe("coder");
    expect(compiled.role).toBe("engineer");
    expect(compiled.system_prompt).toBe("You write code.");
    expect(compiled.tools).toEqual([{ name: "file_read", config: { root: "/src" } }]);
    expect(compiled.model_name).toBe("claude-3-opus");

    // Also check YAML string
    expect(result.yaml).toContain("model_name: claude-3-opus");
    expect(result.yaml).toContain("role: engineer");
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
      nodes: [mockNode("b1", "placeholder")],
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
