/**
 * YAML parser workflow structure coverage.
 *
 * These tests verify that parseWorkflowYamlToGraph maps every snake_case YAML
 * field to its camelCase StepNodeData counterpart.
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
// Souls section parsed
// ===========================================================================

describe("Souls section parsed", () => {
  it("YAML souls section is parsed without error (inline souls are valid)", () => {
    const yaml = makeYaml(
      { step1: { type: "linear", soul_ref: "analyst" } },
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
    // Inline souls are valid shorthand and should not emit a deprecation warning.
    expect(result.error).toBeUndefined();
  });
});

// ===========================================================================
// 4. Config section parsed
// ===========================================================================

describe("Config section parsed", () => {
  it("YAML config section populates ParseWorkflowResult.config", () => {
    const yaml = makeYaml(
      { step1: { type: "linear", soul_ref: "agent" } },
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
  it("minimal linear block does NOT have unrelated fields as keys", () => {
    const yaml = makeYaml({
      step1: { type: "linear" },
    });
    const data = parseFirst(yaml);
    expect(data.stepType).toBe("linear");

    // These fields should NOT exist as keys on data
    const keys = Object.keys(data);
    expect(keys).not.toContain("soulRef");
    expect(keys).not.toContain("soulRefs");
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
    expect(keys).not.toContain("failureContextKeys");
    expect(keys).not.toContain("retryConfig");
  });

  it("linear block does NOT have loop/code fields", () => {
    const yaml = makeYaml({
      step1: { type: "linear", soul_ref: "analyst" },
    });
    const data = parseFirst(yaml);
    const keys = Object.keys(data);
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
        type: "dispatch",
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
        start: { type: "linear" },
        middle: { type: "linear" },
        end: { type: "linear" },
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
        dispatch_step: { type: "dispatch", soul_ref: "classifier" },
        approve: { type: "linear" },
        reject: { type: "linear" },
      },
      workflow: {
        name: "test",
        entry: "dispatch_step",
        transitions: [],
        conditional_transitions: [
          { from: "dispatch_step", approved: "approve", rejected: "reject" },
        ],
      },
    });
    const result = parseWorkflowYamlToGraph(yaml);
    // Should have 2 edges: dispatch_step->approve and dispatch_step->reject
    expect(result.edges).toHaveLength(2);
    const targets = result.edges.map((e) => e.target).sort();
    expect(targets).toEqual(["approve", "reject"]);
    expect(result.edges.every((e) => e.source === "dispatch_step")).toBe(true);
  });

  it("terminal transitions (to: null) do not create edges", () => {
    const yaml = dump({
      version: "1.0",
      blocks: {
        start: { type: "linear" },
        end: { type: "linear" },
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
      a: { type: "linear" },
      b: { type: "linear" },
      c: { type: "linear" },
    });
    const result = parseWorkflowYamlToGraph(yaml);
    expect(result.nodes).toHaveLength(3);
    // Default grid: 280x160, 4 per row
    expect(result.nodes[0].position).toEqual({ x: 0, y: 0 });
    expect(result.nodes[1].position).toEqual({ x: 280, y: 0 });
    expect(result.nodes[2].position).toEqual({ x: 560, y: 0 });
  });

  it("merges persisted node positions and viewport", () => {
    const yaml = dump({
      version: "1.0",
      blocks: {
        step_a: { type: "linear" },
        step_b: { type: "linear" },
      },
      workflow: {
        name: "Demo",
        entry: "step_a",
        transitions: [{ from: "step_a", to: "step_b" }],
      },
    });

    const result = parseWorkflowYamlToGraph(yaml, {
      nodes: [
        { id: "step_a", position: { x: 120, y: 240 } },
        { id: "step_b", position: { x: 400, y: 240 } },
      ],
      edges: [],
      viewport: { x: 10, y: 20, zoom: 0.8 },
      selected_node_id: "step_a",
      canvas_mode: "dag",
    });

    expect(result.error).toBeUndefined();
    expect(result.nodes.find((node) => node.id === "step_a")?.position).toEqual({
      x: 120,
      y: 240,
    });
    expect(result.nodes.find((node) => node.id === "step_b")?.position).toEqual({
      x: 400,
      y: 240,
    });
    expect(result.viewport).toEqual({ x: 10, y: 20, zoom: 0.8 });
    expect(result.edges).toHaveLength(1);
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
  it("type: retry is not a known block type", () => {
    const yaml = makeYaml({
      step1: {
        type: "retry",
        inner_block_ref: "flaky_step",
        max_retries: 3,
        provide_error_context: true,
      },
    });
    const result = parseWorkflowYamlToGraph(yaml);

    // "retry" is accepted as a generic unknown type with no special handling.
    expect(result.nodes).toHaveLength(1);
    expect(result.nodes[0].data.stepType).toBe("retry");
  });
});

// ===========================================================================
// 10. Generic editor parsing contract
// ===========================================================================

describe("Generic editor parsing contract", () => {
  it("preserves unknown block types for downstream validation", () => {
    const yaml = makeYaml({
      step1: { type: "custom_branch", soul_refs: ["a", "b"] },
    });
    const result = parseWorkflowYamlToGraph(yaml);
    expect(result.error).toBeUndefined();
    expect(result.nodes[0].data.stepType).toBe("custom_branch");
  });
});
