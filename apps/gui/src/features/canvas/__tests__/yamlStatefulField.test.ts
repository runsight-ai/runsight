/**
 * RED-TEAM tests for RUN-196: Frontend type updates for `stateful` field.
 *
 * Validates:
 * - StepNodeData and BlockDef accept `stateful?: boolean`
 * - Compiler emits `stateful` to YAML when set, omits when absent
 * - Parser reads `stateful` from YAML into node data
 * - Round-trip: stateful survives compile -> parse -> compile
 *
 * These tests MUST FAIL until the Green Team implements the feature.
 */

import { describe, it, expect, test } from "vitest";
import { compileGraphToWorkflowYaml } from "../yamlCompiler";
import { parseWorkflowYamlToGraph } from "../yamlParser";
import type { StepNodeData, StepType, BlockDef, SoulDef } from "../../../types/schemas/canvas";
import type { Node, Edge } from "@xyflow/react";

// ---------------------------------------------------------------------------
// Helpers (copied from yamlRoundTrip.test.ts)
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
  souls?: Record<string, SoulDef>;
  config?: Record<string, unknown>;
}

/**
 * Core round-trip: compile -> parse -> compile.
 * Returns both YAML strings and compiled documents for assertion.
 */
function roundTrip(input: CompileInput) {
  const { yaml: yaml1, workflowDocument: doc1 } = compileGraphToWorkflowYaml(input);
  const parsed = parseWorkflowYamlToGraph(yaml1);

  // Rebuild compile input from parsed result
  const input2: CompileInput = {
    nodes: parsed.nodes,
    edges: parsed.edges,
    souls: parsed.souls,
    config: parsed.config,
    workflowName: input.workflowName,
  };
  const { yaml: yaml2, workflowDocument: doc2 } = compileGraphToWorkflowYaml(input2);

  return { yaml1, yaml2, doc1, doc2, parsed };
}

// ===========================================================================
// 1. Type existence tests
// ===========================================================================

describe("Type existence: stateful field", () => {
  it("StepNodeData should accept stateful: true without type errors", () => {
    // This test validates that the StepNodeData interface includes stateful?.
    // If the field is missing from the interface, TypeScript compilation will fail.
    const node = mockNode("typed_block", "linear", {
      soulRef: "agent1",
      stateful: true,
    } as Partial<StepNodeData>);

    expect(node.data.stateful).toBe(true);
  });

  it("StepNodeData should accept stateful: false without type errors", () => {
    const node = mockNode("typed_block", "linear", {
      soulRef: "agent1",
      stateful: false,
    } as Partial<StepNodeData>);

    expect(node.data.stateful).toBe(false);
  });

  it("StepNodeData should allow stateful to be undefined (omitted)", () => {
    const node = mockNode("typed_block", "linear", { soulRef: "agent1" });

    expect(node.data.stateful).toBeUndefined();
  });

  it("BlockDef should accept stateful: true without type errors", () => {
    // This validates that BlockDef includes `stateful?: boolean`.
    // Without the field, accessing block.stateful would be a TS error.
    const block: BlockDef = {
      type: "linear",
      soul_ref: "agent1",
      stateful: true,
    } as BlockDef;

    expect(block.stateful).toBe(true);
  });

  it("BlockDef should accept stateful: false without type errors", () => {
    const block: BlockDef = {
      type: "linear",
      soul_ref: "agent1",
      stateful: false,
    } as BlockDef;

    expect(block.stateful).toBe(false);
  });
});

// ===========================================================================
// 2. Compiler tests
// ===========================================================================

describe("Compiler: stateful field", () => {
  it("node with stateful: true compiles to BlockDef with stateful: true", () => {
    const node = mockNode("stateful_block", "linear", {
      soulRef: "agent1",
      stateful: true,
    } as Partial<StepNodeData>);

    const { workflowDocument: doc } = compileGraphToWorkflowYaml({
      nodes: [node],
      edges: [],
    });

    const block = doc.blocks["stateful_block"] as Record<string, unknown>;
    expect(block.stateful).toBe(true);
  });

  it("node with stateful: false compiles to BlockDef with stateful: false", () => {
    const node = mockNode("stateful_block", "linear", {
      soulRef: "agent1",
      stateful: false,
    } as Partial<StepNodeData>);

    const { workflowDocument: doc } = compileGraphToWorkflowYaml({
      nodes: [node],
      edges: [],
    });

    const block = doc.blocks["stateful_block"] as Record<string, unknown>;
    expect(block.stateful).toBe(false);
  });

  it("node without stateful does NOT have stateful key in compiled BlockDef", () => {
    const node = mockNode("clean_block", "linear", { soulRef: "agent1" });

    const { workflowDocument: doc } = compileGraphToWorkflowYaml({
      nodes: [node],
      edges: [],
    });

    const block = doc.blocks["clean_block"] as Record<string, unknown>;
    expect(block).not.toHaveProperty("stateful");
  });

  it("stateful: true appears in compiled YAML string", () => {
    const node = mockNode("stateful_block", "linear", {
      soulRef: "agent1",
      stateful: true,
    } as Partial<StepNodeData>);

    const { yaml } = compileGraphToWorkflowYaml({
      nodes: [node],
      edges: [],
    });

    expect(yaml).toContain("stateful: true");
  });

  it("stateful is NOT in compiled YAML string when absent", () => {
    const node = mockNode("clean_block", "linear", { soulRef: "agent1" });

    const { yaml } = compileGraphToWorkflowYaml({
      nodes: [node],
      edges: [],
    });

    expect(yaml).not.toContain("stateful");
  });
});

// ===========================================================================
// 3. Parser tests
// ===========================================================================

describe("Parser: stateful field", () => {
  it("YAML with stateful: true on a block parses to node data with stateful: true", () => {
    const yamlText = `
version: "1.0"
blocks:
  my_block:
    type: linear
    soul_ref: agent1
    stateful: true
workflow:
  name: Workflow
  entry: my_block
  transitions: []
`;

    const result = parseWorkflowYamlToGraph(yamlText);
    const node = result.nodes.find((n) => n.id === "my_block");

    expect(node).toBeDefined();
    expect(node!.data.stateful).toBe(true);
  });

  it("YAML with stateful: false on a block parses to node data with stateful: false", () => {
    const yamlText = `
version: "1.0"
blocks:
  my_block:
    type: linear
    soul_ref: agent1
    stateful: false
workflow:
  name: Workflow
  entry: my_block
  transitions: []
`;

    const result = parseWorkflowYamlToGraph(yamlText);
    const node = result.nodes.find((n) => n.id === "my_block");

    expect(node).toBeDefined();
    expect(node!.data.stateful).toBe(false);
  });

  it("YAML without stateful on a block parses to node data with stateful undefined", () => {
    const yamlText = `
version: "1.0"
blocks:
  my_block:
    type: linear
    soul_ref: agent1
workflow:
  name: Workflow
  entry: my_block
  transitions: []
`;

    const result = parseWorkflowYamlToGraph(yamlText);
    const node = result.nodes.find((n) => n.id === "my_block");

    expect(node).toBeDefined();
    expect(node!.data.stateful).toBeUndefined();
  });
});

// ===========================================================================
// 4. Round-trip tests
// ===========================================================================

describe("Round-trip: stateful field", () => {
  it("stateful: true survives compile -> parse -> compile", () => {
    const node = mockNode("stateful_block", "linear", {
      soulRef: "agent1",
      stateful: true,
    } as Partial<StepNodeData>);

    const { doc1, doc2, yaml1, yaml2 } = roundTrip({ nodes: [node], edges: [] });

    // Block-level equality
    expect(doc2.blocks["stateful_block"]).toEqual(doc1.blocks["stateful_block"]);

    // Verify stateful is present in both passes
    const block1 = doc1.blocks["stateful_block"] as Record<string, unknown>;
    const block2 = doc2.blocks["stateful_block"] as Record<string, unknown>;
    expect(block1.stateful).toBe(true);
    expect(block2.stateful).toBe(true);

    // YAML string equality
    expect(yaml2).toBe(yaml1);
  });

  it("stateful: false survives compile -> parse -> compile", () => {
    const node = mockNode("stateful_block", "linear", {
      soulRef: "agent1",
      stateful: false,
    } as Partial<StepNodeData>);

    const { doc1, doc2, yaml1, yaml2 } = roundTrip({ nodes: [node], edges: [] });

    const block1 = doc1.blocks["stateful_block"] as Record<string, unknown>;
    const block2 = doc2.blocks["stateful_block"] as Record<string, unknown>;
    expect(block1.stateful).toBe(false);
    expect(block2.stateful).toBe(false);

    expect(yaml2).toBe(yaml1);
  });

  it("block without stateful — omitted in both passes (no noise)", () => {
    const node = mockNode("clean_block", "linear", { soulRef: "agent1" });

    const { doc1, doc2, yaml1, yaml2 } = roundTrip({ nodes: [node], edges: [] });

    const block1 = doc1.blocks["clean_block"] as Record<string, unknown>;
    const block2 = doc2.blocks["clean_block"] as Record<string, unknown>;
    expect(block1).not.toHaveProperty("stateful");
    expect(block2).not.toHaveProperty("stateful");

    expect(yaml1).not.toContain("stateful");
    expect(yaml2).not.toContain("stateful");

    expect(yaml2).toBe(yaml1);
  });

  test.each<[string, StepType, Partial<StepNodeData>]>([
    ["linear", "linear", { soulRef: "agent1", stateful: true } as Partial<StepNodeData>],
    ["loop", "loop", { innerBlockRefs: ["step_a"], maxRounds: 3, stateful: true } as Partial<StepNodeData>],
    ["fanout", "fanout", { soulRefs: ["a", "b"], stateful: true } as Partial<StepNodeData>],
  ])("stateful: true round-trips on %s block type", (_label, stepType, fields) => {
    const node = mockNode("block1", stepType, fields);

    const { doc1, doc2 } = roundTrip({ nodes: [node], edges: [] });

    const block1 = doc1.blocks["block1"] as Record<string, unknown>;
    const block2 = doc2.blocks["block1"] as Record<string, unknown>;
    expect(block1.stateful).toBe(true);
    expect(block2.stateful).toBe(true);
    expect(doc2.blocks["block1"]).toEqual(doc1.blocks["block1"]);
  });
});

// ===========================================================================
// 5. Edge cases
// ===========================================================================

describe("Edge cases: stateful field", () => {
  it("stateful: true combined with retry_config round-trips correctly", () => {
    const node = mockNode("combo_block", "linear", {
      soulRef: "agent1",
      stateful: true,
      retryConfig: {
        maxAttempts: 3,
        backoff: "exponential",
        backoffBaseSeconds: 2,
      },
    } as Partial<StepNodeData>);

    const { doc1, doc2 } = roundTrip({ nodes: [node], edges: [] });

    const block1 = doc1.blocks["combo_block"] as Record<string, unknown>;
    const block2 = doc2.blocks["combo_block"] as Record<string, unknown>;
    expect(block1.stateful).toBe(true);
    expect(block1).toHaveProperty("retry_config");
    expect(block2.stateful).toBe(true);
    expect(block2).toHaveProperty("retry_config");
    expect(doc2.blocks["combo_block"]).toEqual(doc1.blocks["combo_block"]);
  });

  it("stateful: true combined with output_conditions round-trips correctly", () => {
    const node = mockNode("combo_block", "linear", {
      soulRef: "agent1",
      stateful: true,
      outputConditions: [
        { case_id: "done", default: true },
      ],
    } as Partial<StepNodeData>);

    const { doc1, doc2 } = roundTrip({ nodes: [node], edges: [] });

    const block1 = doc1.blocks["combo_block"] as Record<string, unknown>;
    const block2 = doc2.blocks["combo_block"] as Record<string, unknown>;
    expect(block1.stateful).toBe(true);
    expect(block1).toHaveProperty("output_conditions");
    expect(block2.stateful).toBe(true);
    expect(block2).toHaveProperty("output_conditions");
    expect(doc2.blocks["combo_block"]).toEqual(doc1.blocks["combo_block"]);
  });

  it("mixed workflow: some blocks with stateful, some without — each preserves its own setting", () => {
    const nodes = [
      mockNode("stateful_a", "linear", {
        soulRef: "agent1",
        stateful: true,
      } as Partial<StepNodeData>),
      mockNode("plain_b", "linear", {
        soulRef: "agent2",
      }),
      mockNode("stateful_c", "fanout", {
        soulRefs: ["agent1", "agent2"],
        stateful: false,
      } as Partial<StepNodeData>),
    ];
    const edges = [
      mockEdge("stateful_a", "plain_b"),
      mockEdge("plain_b", "stateful_c"),
    ];

    const { doc1, doc2, yaml1, yaml2 } = roundTrip({ nodes, edges });

    // stateful_a: stateful: true
    const a1 = doc1.blocks["stateful_a"] as Record<string, unknown>;
    const a2 = doc2.blocks["stateful_a"] as Record<string, unknown>;
    expect(a1.stateful).toBe(true);
    expect(a2.stateful).toBe(true);

    // plain_b: no stateful key
    const b1 = doc1.blocks["plain_b"] as Record<string, unknown>;
    const b2 = doc2.blocks["plain_b"] as Record<string, unknown>;
    expect(b1).not.toHaveProperty("stateful");
    expect(b2).not.toHaveProperty("stateful");

    // stateful_c: stateful: false
    const c1 = doc1.blocks["stateful_c"] as Record<string, unknown>;
    const c2 = doc2.blocks["stateful_c"] as Record<string, unknown>;
    expect(c1.stateful).toBe(false);
    expect(c2.stateful).toBe(false);

    // Full YAML string equality
    expect(yaml2).toBe(yaml1);
  });
});
