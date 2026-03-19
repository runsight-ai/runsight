/**
 * Red-team tests for RUN-119: Parser reads ALL block fields back into StepNodeData.
 *
 * These tests verify that parseWorkflowYamlToGraph maps every snake_case YAML
 * field to its camelCase StepNodeData counterpart. They are expected to FAIL
 * against the current implementation (which only reads `type`).
 */
import { describe, it, expect } from "vitest";
import { dump } from "js-yaml";
import { parseWorkflowYamlToGraph } from "../yamlParser";
import type { StepNodeData } from "../../../types/schemas/canvas";

// ---------------------------------------------------------------------------
// Helper: build a minimal valid YAML string
// ---------------------------------------------------------------------------

function makeYaml(
  blocks: Record<string, object>,
  opts?: { souls?: object; config?: object },
): string {
  return dump({
    version: "1.0",
    ...(opts?.config ? { config: opts.config } : {}),
    ...(opts?.souls ? { souls: opts.souls } : {}),
    blocks,
    workflow: {
      name: "test",
      entry: Object.keys(blocks)[0] ?? "start",
      transitions: [],
    },
  });
}

/** Parse and return the first node's data for convenience. */
function parseFirst(yaml: string): StepNodeData {
  const result = parseWorkflowYamlToGraph(yaml);
  expect(result.nodes).toHaveLength(1);
  return result.nodes[0].data;
}

// ===========================================================================
// 1. Per-type field parsing
// ===========================================================================

describe("Per-type field parsing", () => {
  it("linear: soul_ref -> soulRef", () => {
    const yaml = makeYaml({
      step1: { type: "linear", soul_ref: "analyst" },
    });
    const data = parseFirst(yaml);
    expect(data.stepType).toBe("linear");
    expect(data.soulRef).toBe("analyst");
  });

  it("fanout: soul_refs -> soulRefs", () => {
    const yaml = makeYaml({
      step1: { type: "fanout", soul_refs: ["a", "b", "c"] },
    });
    const data = parseFirst(yaml);
    expect(data.stepType).toBe("fanout");
    expect(data.soulRefs).toEqual(["a", "b", "c"]);
  });

  it("synthesize: soul_ref + input_block_ids -> soulRef + inputBlockIds", () => {
    const yaml = makeYaml({
      step1: {
        type: "synthesize",
        soul_ref: "summarizer",
        input_block_ids: ["step_a", "step_b"],
      },
    });
    const data = parseFirst(yaml);
    expect(data.stepType).toBe("synthesize");
    expect(data.soulRef).toBe("summarizer");
    expect(data.inputBlockIds).toEqual(["step_a", "step_b"]);
  });

  it("debate: soul_a_ref + soul_b_ref + iterations -> soulARef + soulBRef + iterations", () => {
    const yaml = makeYaml({
      step1: {
        type: "debate",
        soul_a_ref: "optimist",
        soul_b_ref: "pessimist",
        iterations: 3,
      },
    });
    const data = parseFirst(yaml);
    expect(data.stepType).toBe("debate");
    expect(data.soulARef).toBe("optimist");
    expect(data.soulBRef).toBe("pessimist");
    expect(data.iterations).toBe(3);
  });

  it("message_bus: soul_refs + iterations -> soulRefs + iterations", () => {
    const yaml = makeYaml({
      step1: {
        type: "message_bus",
        soul_refs: ["agent1", "agent2"],
        iterations: 5,
      },
    });
    const data = parseFirst(yaml);
    expect(data.stepType).toBe("message_bus");
    expect(data.soulRefs).toEqual(["agent1", "agent2"]);
    expect(data.iterations).toBe(5);
  });

  it("router: soul_ref + condition_ref -> soulRef + conditionRef", () => {
    const yaml = makeYaml({
      step1: {
        type: "router",
        soul_ref: "classifier",
        condition_ref: "route_cond",
      },
    });
    const data = parseFirst(yaml);
    expect(data.stepType).toBe("router");
    expect(data.soulRef).toBe("classifier");
    expect(data.conditionRef).toBe("route_cond");
  });

  it("team_lead: soul_ref + failure_context_keys -> soulRef + failureContextKeys", () => {
    const yaml = makeYaml({
      step1: {
        type: "team_lead",
        soul_ref: "lead",
        failure_context_keys: ["error_msg", "stack_trace"],
      },
    });
    const data = parseFirst(yaml);
    expect(data.stepType).toBe("team_lead");
    expect(data.soulRef).toBe("lead");
    expect(data.failureContextKeys).toEqual(["error_msg", "stack_trace"]);
  });

  it("engineering_manager: soul_ref -> soulRef", () => {
    const yaml = makeYaml({
      step1: { type: "engineering_manager", soul_ref: "em" },
    });
    const data = parseFirst(yaml);
    expect(data.stepType).toBe("engineering_manager");
    expect(data.soulRef).toBe("em");
  });

  it("gate: soul_ref + eval_key + extract_field -> soulRef + evalKey + extractField", () => {
    const yaml = makeYaml({
      step1: {
        type: "gate",
        soul_ref: "evaluator",
        eval_key: "result.approved",
        extract_field: "details",
      },
    });
    const data = parseFirst(yaml);
    expect(data.stepType).toBe("gate");
    expect(data.soulRef).toBe("evaluator");
    expect(data.evalKey).toBe("result.approved");
    expect(data.extractField).toBe("details");
  });

  it("placeholder: description -> description", () => {
    const yaml = makeYaml({
      step1: { type: "placeholder", description: "TODO: implement" },
    });
    const data = parseFirst(yaml);
    expect(data.stepType).toBe("placeholder");
    expect(data.description).toBe("TODO: implement");
  });

  it("file_writer: output_path + content_key -> outputPath + contentKey", () => {
    const yaml = makeYaml({
      step1: {
        type: "file_writer",
        output_path: "/tmp/report.md",
        content_key: "report_content",
      },
    });
    const data = parseFirst(yaml);
    expect(data.stepType).toBe("file_writer");
    expect(data.outputPath).toBe("/tmp/report.md");
    expect(data.contentKey).toBe("report_content");
  });

  it("code: code + timeout_seconds + allowed_imports -> code + timeoutSeconds + allowedImports", () => {
    const yaml = makeYaml({
      step1: {
        type: "code",
        code: "print('hello')",
        timeout_seconds: 60,
        allowed_imports: ["json", "math"],
      },
    });
    const data = parseFirst(yaml);
    expect(data.stepType).toBe("code");
    expect(data.code).toBe("print('hello')");
    expect(data.timeoutSeconds).toBe(60);
    expect(data.allowedImports).toEqual(["json", "math"]);
  });

  it("loop: inner_block_refs + max_rounds + break_condition + carry_context -> innerBlockRefs + maxRounds + breakCondition + carryContext", () => {
    const yaml = makeYaml({
      step1: {
        type: "loop",
        inner_block_refs: ["step_a", "step_b"],
        max_rounds: 5,
        break_condition: "result.converged == true",
        carry_context: {
          enabled: true,
          mode: "last",
          source_blocks: ["step_b"],
          inject_as: "previous_output",
        },
      },
    });
    const data = parseFirst(yaml);
    expect(data.stepType).toBe("loop");
    expect(data.innerBlockRefs).toEqual(["step_a", "step_b"]);
    expect(data.maxRounds).toBe(5);
    expect(data.breakCondition).toBe("result.converged == true");
    expect(data.carryContext).toEqual({
      enabled: true,
      mode: "last",
      sourceBlocks: ["step_b"],
      injectAs: "previous_output",
    });
  });

  it("loop: minimal with only inner_block_refs", () => {
    const yaml = makeYaml({
      step1: {
        type: "loop",
        inner_block_refs: ["single_step"],
      },
    });
    const data = parseFirst(yaml);
    expect(data.stepType).toBe("loop");
    expect(data.innerBlockRefs).toEqual(["single_step"]);
    expect(Object.keys(data)).not.toContain("maxRounds");
    expect(Object.keys(data)).not.toContain("breakCondition");
    expect(Object.keys(data)).not.toContain("carryContext");
  });

  it("workflow: workflow_ref + max_depth -> workflowRef + maxDepth", () => {
    const yaml = makeYaml({
      step1: {
        type: "workflow",
        workflow_ref: "sub_workflow",
        max_depth: 5,
      },
    });
    const data = parseFirst(yaml);
    expect(data.stepType).toBe("workflow");
    expect(data.workflowRef).toBe("sub_workflow");
    expect(data.maxDepth).toBe(5);
  });
});

// ===========================================================================
// 2. Universal fields parsed
// ===========================================================================

describe("Universal fields parsed", () => {
  it("output_conditions -> outputConditions", () => {
    const yaml = makeYaml({
      step1: {
        type: "linear",
        soul_ref: "analyst",
        output_conditions: [
          { case_id: "happy", condition_group: { combinator: "and", conditions: [{ eval_key: "score", operator: "gte", value: 80 }] } },
          { case_id: "fallback", default: true },
        ],
      },
    });
    const data = parseFirst(yaml);
    expect(data.outputConditions).toBeDefined();
    expect(data.outputConditions).toHaveLength(2);
    expect(data.outputConditions![0].case_id).toBe("happy");
    expect(data.outputConditions![1].default).toBe(true);
  });

  it("inputs -> inputs", () => {
    const yaml = makeYaml({
      step1: {
        type: "linear",
        soul_ref: "analyst",
        inputs: { context: { from: "upstream.output" } },
      },
    });
    const data = parseFirst(yaml);
    expect(data.inputs).toBeDefined();
    expect(data.inputs).toEqual({ context: { from: "upstream.output" } });
  });

  it("outputs -> outputs", () => {
    const yaml = makeYaml({
      step1: {
        type: "linear",
        soul_ref: "analyst",
        outputs: { summary: "string", detail: "string" },
      },
    });
    const data = parseFirst(yaml);
    expect(data.outputs).toBeDefined();
    expect(data.outputs).toEqual({ summary: "string", detail: "string" });
  });

  it("retry_config -> retryConfig (on linear block)", () => {
    const yaml = makeYaml({
      step1: {
        type: "linear",
        soul_ref: "analyst",
        retry_config: {
          max_attempts: 3,
          backoff: "exponential",
          backoff_base_seconds: 2,
          non_retryable_errors: ["AuthError"],
        },
      },
    });
    const data = parseFirst(yaml);
    expect(data.retryConfig).toBeDefined();
    expect(data.retryConfig).toEqual({
      maxAttempts: 3,
      backoff: "exponential",
      backoffBaseSeconds: 2,
      nonRetryableErrors: ["AuthError"],
    });
  });

  it("retry_config -> retryConfig (on code block)", () => {
    const yaml = makeYaml({
      step1: {
        type: "code",
        code: "run()",
        retry_config: {
          max_attempts: 5,
          backoff: "fixed",
          backoff_base_seconds: 1,
        },
      },
    });
    const data = parseFirst(yaml);
    expect(data.retryConfig).toBeDefined();
    expect(data.retryConfig).toEqual({
      maxAttempts: 5,
      backoff: "fixed",
      backoffBaseSeconds: 1,
    });
  });

  it("retry_config -> retryConfig (on loop block)", () => {
    const yaml = makeYaml({
      step1: {
        type: "loop",
        inner_block_refs: ["step_a"],
        retry_config: {
          max_attempts: 2,
          backoff: "fixed",
          backoff_base_seconds: 10,
        },
      },
    });
    const data = parseFirst(yaml);
    expect(data.stepType).toBe("loop");
    expect(data.retryConfig).toBeDefined();
    expect(data.retryConfig!.maxAttempts).toBe(2);
  });
});

// ===========================================================================
// 3. Souls section parsed
// ===========================================================================

describe("Souls section parsed", () => {
  it("YAML souls section populates ParseWorkflowResult.souls", () => {
    const yaml = makeYaml(
      { step1: { type: "placeholder" } },
      {
        souls: {
          analyst: {
            id: "analyst",
            role: "Data Analyst",
            system_prompt: "You analyze data.",
            model_name: "gpt-4",
          },
        },
      },
    );
    const result = parseWorkflowYamlToGraph(yaml);
    // The result should expose souls from the YAML
    expect((result as any).souls).toBeDefined();
    expect((result as any).souls.analyst).toBeDefined();
    expect((result as any).souls.analyst.id).toBe("analyst");
    expect((result as any).souls.analyst.role).toBe("Data Analyst");
  });
});

// ===========================================================================
// 4. Config section parsed
// ===========================================================================

describe("Config section parsed", () => {
  it("YAML config section populates ParseWorkflowResult.config", () => {
    const yaml = makeYaml(
      { step1: { type: "placeholder" } },
      {
        config: {
          max_concurrent: 4,
          timeout: 300,
          provider: "openai",
        },
      },
    );
    const result = parseWorkflowYamlToGraph(yaml);
    expect((result as any).config).toBeDefined();
    expect((result as any).config.max_concurrent).toBe(4);
    expect((result as any).config.provider).toBe("openai");
  });
});

// ===========================================================================
// 5. Undefined fields not polluted
// ===========================================================================

describe("Undefined fields not polluted", () => {
  it("minimal placeholder block does NOT have soul/iteration fields as keys", () => {
    const yaml = makeYaml({
      step1: { type: "placeholder" },
    });
    const data = parseFirst(yaml);
    expect(data.stepType).toBe("placeholder");

    // These fields should NOT exist as keys on data
    const keys = Object.keys(data);
    expect(keys).not.toContain("soulRef");
    expect(keys).not.toContain("soulRefs");
    expect(keys).not.toContain("soulARef");
    expect(keys).not.toContain("soulBRef");
    expect(keys).not.toContain("iterations");
    expect(keys).not.toContain("workflowRef");
    expect(keys).not.toContain("evalKey");
    expect(keys).not.toContain("innerBlockRefs");
    expect(keys).not.toContain("maxRounds");
    expect(keys).not.toContain("breakCondition");
    expect(keys).not.toContain("carryContext");
    expect(keys).not.toContain("code");
    expect(keys).not.toContain("timeoutSeconds");
    expect(keys).not.toContain("allowedImports");
    expect(keys).not.toContain("outputPath");
    expect(keys).not.toContain("contentKey");
    expect(keys).not.toContain("conditionRef");
    expect(keys).not.toContain("failureContextKeys");
    expect(keys).not.toContain("retryConfig");
  });

  it("linear block does NOT have debate/loop/code fields", () => {
    const yaml = makeYaml({
      step1: { type: "linear", soul_ref: "analyst" },
    });
    const data = parseFirst(yaml);
    const keys = Object.keys(data);
    expect(keys).not.toContain("soulARef");
    expect(keys).not.toContain("soulBRef");
    expect(keys).not.toContain("iterations");
    expect(keys).not.toContain("innerBlockRefs");
    expect(keys).not.toContain("maxRounds");
    expect(keys).not.toContain("breakCondition");
    expect(keys).not.toContain("carryContext");
    expect(keys).not.toContain("code");
    expect(keys).not.toContain("timeoutSeconds");
  });
});

// ===========================================================================
// 6. Complex structures parsed (output_conditions with nested condition_group)
// ===========================================================================

describe("Complex structures parsed", () => {
  it("output_conditions with nested condition_group are correctly parsed as CaseDef array", () => {
    const yaml = makeYaml({
      step1: {
        type: "router",
        soul_ref: "classifier",
        output_conditions: [
          {
            case_id: "high_priority",
            condition_group: {
              combinator: "and",
              conditions: [
                { eval_key: "priority", operator: "eq", value: "high" },
                { eval_key: "confidence", operator: "gte", value: 0.9 },
              ],
            },
          },
          {
            case_id: "medium_priority",
            condition_group: {
              combinator: "or",
              conditions: [
                { eval_key: "priority", operator: "eq", value: "medium" },
              ],
            },
          },
          { case_id: "default_case", default: true },
        ],
      },
    });
    const data = parseFirst(yaml);
    expect(data.outputConditions).toBeDefined();
    expect(data.outputConditions).toHaveLength(3);

    const first = data.outputConditions![0];
    expect(first.case_id).toBe("high_priority");
    expect(first.condition_group).toBeDefined();
    expect(first.condition_group!.combinator).toBe("and");
    expect(first.condition_group!.conditions).toHaveLength(2);
    expect(first.condition_group!.conditions[0].eval_key).toBe("priority");
    expect(first.condition_group!.conditions[0].operator).toBe("eq");
    expect(first.condition_group!.conditions[0].value).toBe("high");
    expect(first.condition_group!.conditions[1].eval_key).toBe("confidence");
    expect(first.condition_group!.conditions[1].operator).toBe("gte");
    expect(first.condition_group!.conditions[1].value).toBe(0.9);

    const last = data.outputConditions![2];
    expect(last.case_id).toBe("default_case");
    expect(last.default).toBe(true);
  });
});

// ===========================================================================
// 7. Multiline code parsed
// ===========================================================================

describe("Multiline code parsed", () => {
  it("YAML code block with | scalar preserves the multiline string", () => {
    // Use a raw YAML string to test the | literal block scalar
    const yaml = `
version: "1.0"
blocks:
  compute:
    type: code
    code: |
      import json
      data = json.loads(input)
      result = {"count": len(data)}
      print(json.dumps(result))
    timeout_seconds: 45
    allowed_imports:
      - json
workflow:
  name: test
  entry: compute
  transitions: []
`;
    const data = parseFirst(yaml);
    expect(data.stepType).toBe("code");
    expect(data.code).toContain("import json");
    expect(data.code).toContain("data = json.loads(input)");
    expect(data.code).toContain("result = {\"count\": len(data)}");
    expect(data.code).toContain("print(json.dumps(result))");
    expect(data.timeoutSeconds).toBe(45);
    expect(data.allowedImports).toEqual(["json"]);
  });
});

// ===========================================================================
// 8. Existing behavior preserved (transitions and conditional_transitions)
// ===========================================================================

describe("Existing behavior preserved", () => {
  it("transitions create correct edges", () => {
    const yaml = dump({
      version: "1.0",
      blocks: {
        start: { type: "placeholder" },
        middle: { type: "placeholder" },
        end: { type: "placeholder" },
      },
      workflow: {
        name: "test",
        entry: "start",
        transitions: [
          { from: "start", to: "middle" },
          { from: "middle", to: "end" },
        ],
      },
    });
    const result = parseWorkflowYamlToGraph(yaml);
    expect(result.edges).toHaveLength(2);
    expect(result.edges[0]).toMatchObject({ source: "start", target: "middle" });
    expect(result.edges[1]).toMatchObject({ source: "middle", target: "end" });
  });

  it("conditional_transitions create correct edges", () => {
    const yaml = dump({
      version: "1.0",
      blocks: {
        router: { type: "router", soul_ref: "classifier" },
        approve: { type: "placeholder" },
        reject: { type: "placeholder" },
      },
      workflow: {
        name: "test",
        entry: "router",
        transitions: [],
        conditional_transitions: [
          { from: "router", approved: "approve", rejected: "reject" },
        ],
      },
    });
    const result = parseWorkflowYamlToGraph(yaml);
    // Should have 2 edges: router->approve and router->reject
    expect(result.edges).toHaveLength(2);
    const targets = result.edges.map((e) => e.target).sort();
    expect(targets).toEqual(["approve", "reject"]);
    expect(result.edges.every((e) => e.source === "router")).toBe(true);
  });

  it("terminal transitions (to: null) do not create edges", () => {
    const yaml = dump({
      version: "1.0",
      blocks: {
        start: { type: "placeholder" },
        end: { type: "placeholder" },
      },
      workflow: {
        name: "test",
        entry: "start",
        transitions: [
          { from: "start", to: "end" },
          { from: "end", to: null },
        ],
      },
    });
    const result = parseWorkflowYamlToGraph(yaml);
    expect(result.edges).toHaveLength(1);
    expect(result.edges[0]).toMatchObject({ source: "start", target: "end" });
  });

  it("node positions use grid layout when no persisted canvas state", () => {
    const yaml = makeYaml({
      a: { type: "placeholder" },
      b: { type: "placeholder" },
      c: { type: "placeholder" },
    });
    const result = parseWorkflowYamlToGraph(yaml);
    expect(result.nodes).toHaveLength(3);
    // Default grid: 280x160, 4 per row
    expect(result.nodes[0].position).toEqual({ x: 0, y: 0 });
    expect(result.nodes[1].position).toEqual({ x: 280, y: 0 });
    expect(result.nodes[2].position).toEqual({ x: 560, y: 0 });
  });

  it("YAML parse errors return error in result", () => {
    const result = parseWorkflowYamlToGraph("{{invalid yaml");
    expect(result.error).toBeDefined();
    expect(result.nodes).toHaveLength(0);
    expect(result.edges).toHaveLength(0);
  });
});

// ===========================================================================
// 9. Deprecated retry block type
// ===========================================================================

describe("Deprecated retry block type", () => {
  it("type: retry YAML produces parse warning or error", () => {
    const yaml = makeYaml({
      step1: {
        type: "retry",
        inner_block_ref: "flaky_step",
        max_retries: 3,
        provide_error_context: true,
      },
    });
    const result = parseWorkflowYamlToGraph(yaml);

    // The parser should either produce an error/warning or
    // NOT parse it as a valid "retry" stepType (since "retry" is removed from StepType)
    const hasWarning = result.error !== undefined;
    const parsedAsPlaceholder =
      result.nodes.length > 0 && result.nodes[0].data.stepType !== "retry";
    expect(hasWarning || parsedAsPlaceholder).toBe(true);
  });
});
