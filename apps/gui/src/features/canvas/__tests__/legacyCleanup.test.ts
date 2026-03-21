/**
 * RED-TEAM tests for RUN-223: Remove Legacy Hardcoded Maps.
 *
 * After this cleanup, the frontend compiler and parser use ONLY the generic
 * path for all block types — no hardcoded field lists, no camel/snake maps,
 * no known-block-type sets.
 *
 * Tests verify:
 * 1. yamlCompiler.ts has no BLOCK_TYPE_FIELDS constant
 * 2. yamlCompiler.ts has no CAMEL_TO_SNAKE constant
 * 3. yamlCompiler.ts has no SNAKE_TO_CAMEL constant
 * 4. yamlCompiler.ts has no UNIVERSAL_FIELDS constant
 * 5. yamlCompiler.ts has no NESTED_OBJECT_FIELDS constant
 * 6. yamlParser.ts has no KNOWN_BLOCK_TYPES constant
 * 7. Known block types still round-trip correctly after cleanup
 *
 * Expected failures (current state):
 * - yamlCompiler.ts still has all five hardcoded constants
 * - yamlParser.ts still has KNOWN_BLOCK_TYPES
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { dump } from "js-yaml";
import { parseWorkflowYamlToGraph } from "../yamlParser";
import { compileGraphToWorkflowYaml } from "../yamlCompiler";
import type { StepNodeData, StepType, SoulDef } from "../../../types/schemas/canvas";
import type { Node, Edge } from "@xyflow/react";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function readSourceFile(relativePath: string): string {
  const canvasDir = resolve(__dirname, "..");
  return readFileSync(resolve(canvasDir, relativePath), "utf-8");
}

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

function mockNode(
  id: string,
  stepType: string,
  extraData: Partial<StepNodeData> = {},
): Node<StepNodeData> {
  return {
    id,
    type: "canvasNode",
    position: { x: 0, y: 0 },
    data: {
      stepId: id,
      name: id,
      stepType: stepType as StepType,
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

function getBlock(
  doc: { blocks: Record<string, unknown> },
  id: string,
): Record<string, unknown> {
  return doc.blocks[id] as Record<string, unknown>;
}

interface CompileInput {
  nodes: Node<StepNodeData>[];
  edges: Edge[];
  workflowName?: string;
  souls?: Record<string, SoulDef>;
  config?: Record<string, unknown>;
}

function roundTrip(input: CompileInput) {
  const { yaml: yaml1, workflowDocument: doc1 } =
    compileGraphToWorkflowYaml(input);
  const parsed = parseWorkflowYamlToGraph(yaml1);

  const input2: CompileInput = {
    nodes: parsed.nodes,
    edges: parsed.edges,
    souls: parsed.souls,
    config: parsed.config,
    workflowName: input.workflowName,
  };
  const { yaml: yaml2, workflowDocument: doc2 } =
    compileGraphToWorkflowYaml(input2);

  return { yaml1, yaml2, doc1, doc2, parsed };
}

// ===========================================================================
// 1. yamlCompiler.ts — legacy constants removed
// ===========================================================================

describe("Legacy cleanup: yamlCompiler.ts", () => {
  const source = readSourceFile("yamlCompiler.ts");

  it("does not contain BLOCK_TYPE_FIELDS constant", () => {
    expect(source).not.toMatch(/\bBLOCK_TYPE_FIELDS\b/);
  });

  it("does not contain CAMEL_TO_SNAKE constant", () => {
    expect(source).not.toMatch(/\bCAMEL_TO_SNAKE\b/);
  });

  it("does not contain SNAKE_TO_CAMEL constant", () => {
    expect(source).not.toMatch(/\bSNAKE_TO_CAMEL\b/);
  });

  it("does not contain UNIVERSAL_FIELDS constant", () => {
    expect(source).not.toMatch(/\bUNIVERSAL_FIELDS\b/);
  });

  it("does not contain NESTED_OBJECT_FIELDS constant", () => {
    expect(source).not.toMatch(/\bNESTED_OBJECT_FIELDS\b/);
  });

  it("does not contain isKnownType branching logic", () => {
    // The dual-path logic (known type optimized + generic fallback) should
    // be collapsed into a single generic path.
    expect(source).not.toMatch(/\bisKnownType\b/);
  });
});

// ===========================================================================
// 2. yamlParser.ts — legacy constants removed
// ===========================================================================

describe("Legacy cleanup: yamlParser.ts", () => {
  const source = readSourceFile("yamlParser.ts");

  it("does not contain KNOWN_BLOCK_TYPES constant", () => {
    expect(source).not.toMatch(/\bKNOWN_BLOCK_TYPES\b/);
  });

  it("does not contain VALID_STEP_TYPES constant (pre-RUN-221 name)", () => {
    // Guard against the old name being reintroduced
    expect(source).not.toMatch(/\bVALID_STEP_TYPES\b/);
  });

  it("does not contain handledSnakeFields set (generic fallback guard)", () => {
    // The parser should use a single generic path for ALL types,
    // not a known-fields set to gate the generic fallback.
    expect(source).not.toMatch(/\bhandledSnakeFields\b/);
  });
});

// ===========================================================================
// 3. Known block types still round-trip correctly after cleanup
//    (the generic path must handle them as well as the old hardcoded path)
// ===========================================================================

describe("Round-trip after cleanup: known types use generic path", () => {
  it("linear block with soul_ref round-trips", () => {
    const node = mockNode("b1", "linear", { soulRef: "analyst" });
    const { doc1, doc2 } = roundTrip({ nodes: [node], edges: [] });
    expect(getBlock(doc1, "b1").type).toBe("linear");
    expect(getBlock(doc1, "b1").soul_ref).toBe("analyst");
    expect(doc2.blocks["b1"]).toEqual(doc1.blocks["b1"]);
  });

  it("loop block with carry_context round-trips", () => {
    const node = mockNode("b1", "loop", {
      innerBlockRefs: ["step_a"],
      maxRounds: 5,
      breakCondition: "result.done == true",
      carryContext: {
        enabled: true,
        mode: "all",
        sourceBlocks: ["step_a"],
        injectAs: "prior",
      },
    });
    const { doc1, doc2 } = roundTrip({ nodes: [node], edges: [] });
    expect(getBlock(doc1, "b1").type).toBe("loop");
    expect(doc2.blocks["b1"]).toEqual(doc1.blocks["b1"]);
  });

  it("http_request block round-trips all fields", () => {
    const node = mockNode("b1", "http_request", {
      url: "https://api.example.com",
      method: "POST",
      bodyType: "json",
      body: '{"key": "value"}',
      timeoutSeconds: 30,
      expectedStatusCodes: [200, 201],
      retryCount: 3,
      retryBackoff: "exponential",
    });
    const { doc1, doc2 } = roundTrip({ nodes: [node], edges: [] });
    expect(getBlock(doc1, "b1").type).toBe("http_request");
    expect(getBlock(doc1, "b1").url).toBe("https://api.example.com");
    expect(getBlock(doc1, "b1").body_type).toBe("json");
    expect(getBlock(doc1, "b1").expected_status_codes).toEqual([200, 201]);
    expect(doc2.blocks["b1"]).toEqual(doc1.blocks["b1"]);
  });

  it("gate block round-trips", () => {
    const node = mockNode("b1", "gate", {
      soulRef: "gatekeeper",
      evalKey: "quality",
      extractField: "score",
    });
    const { doc1, doc2 } = roundTrip({ nodes: [node], edges: [] });
    expect(getBlock(doc1, "b1").type).toBe("gate");
    expect(getBlock(doc1, "b1").eval_key).toBe("quality");
    expect(doc2.blocks["b1"]).toEqual(doc1.blocks["b1"]);
  });

  it("code block round-trips", () => {
    const node = mockNode("b1", "code", {
      code: "print('hello')",
      timeoutSeconds: 60,
      allowedImports: ["json", "math"],
    });
    const { doc1, doc2 } = roundTrip({ nodes: [node], edges: [] });
    expect(getBlock(doc1, "b1").type).toBe("code");
    expect(getBlock(doc1, "b1").code).toBe("print('hello')");
    expect(doc2.blocks["b1"]).toEqual(doc1.blocks["b1"]);
  });

  it("workflow block with inputs/outputs round-trips", () => {
    const node = mockNode("sub", "workflow", {
      workflowRef: "sub.yaml",
      maxDepth: 3,
      workflowInputs: { query: "parent.user_query" },
      workflowOutputs: { summary: "child.result.summary" },
    });
    const { doc1, doc2 } = roundTrip({ nodes: [node], edges: [] });
    expect(getBlock(doc1, "sub").type).toBe("workflow");
    expect(getBlock(doc1, "sub").workflow_ref).toBe("sub.yaml");
    expect(getBlock(doc1, "sub").inputs).toEqual({
      query: "parent.user_query",
    });
    expect(doc2.blocks["sub"]).toEqual(doc1.blocks["sub"]);
  });

  it("fanout block round-trips", () => {
    const node = mockNode("b1", "fanout", {
      soulRefs: ["analyst1", "analyst2"],
    });
    const { doc1, doc2 } = roundTrip({ nodes: [node], edges: [] });
    expect(getBlock(doc1, "b1").type).toBe("fanout");
    expect(getBlock(doc1, "b1").soul_refs).toEqual(["analyst1", "analyst2"]);
    expect(doc2.blocks["b1"]).toEqual(doc1.blocks["b1"]);
  });

  it("synthesize block round-trips", () => {
    const node = mockNode("b1", "synthesize", {
      soulRef: "synthesizer",
      inputBlockIds: ["step_a", "step_b"],
    });
    const { doc1, doc2 } = roundTrip({ nodes: [node], edges: [] });
    expect(getBlock(doc1, "b1").type).toBe("synthesize");
    expect(getBlock(doc1, "b1").input_block_ids).toEqual([
      "step_a",
      "step_b",
    ]);
    expect(doc2.blocks["b1"]).toEqual(doc1.blocks["b1"]);
  });

  it("router block round-trips", () => {
    const node = mockNode("b1", "router", {
      soulRef: "router_soul",
      conditionRef: "my_condition",
    });
    const { doc1, doc2 } = roundTrip({ nodes: [node], edges: [] });
    expect(getBlock(doc1, "b1").type).toBe("router");
    expect(getBlock(doc1, "b1").condition_ref).toBe("my_condition");
    expect(doc2.blocks["b1"]).toEqual(doc1.blocks["b1"]);
  });
});

// ===========================================================================
// 4. Mixed known + unknown types in same workflow after cleanup
// ===========================================================================

describe("Mixed known + unknown types after cleanup", () => {
  it("workflow with linear, custom_thing, and http_request all round-trip", () => {
    const nodes = [
      mockNode("plan", "linear", { soulRef: "planner" }),
      mockNode("transform", "custom_thing", {
        fooBar: 42,
        bazQux: "hello",
      } as unknown as Partial<StepNodeData>),
      mockNode("fetch", "http_request", {
        url: "https://api.example.com/data",
        method: "GET",
        timeoutSeconds: 15,
      }),
    ];

    const edges = [
      mockEdge("plan", "transform"),
      mockEdge("transform", "fetch"),
    ];

    const { doc1, doc2, yaml1, yaml2 } = roundTrip({ nodes, edges });

    expect(getBlock(doc1, "plan").type).toBe("linear");
    expect(getBlock(doc1, "plan").soul_ref).toBe("planner");
    expect(getBlock(doc1, "transform").type).toBe("custom_thing");
    expect(getBlock(doc1, "transform").foo_bar).toBe(42);
    expect(getBlock(doc1, "fetch").type).toBe("http_request");
    expect(getBlock(doc1, "fetch").url).toBe("https://api.example.com/data");

    expect(doc2.blocks).toEqual(doc1.blocks);
    expect(yaml2).toBe(yaml1);
  });
});

// ===========================================================================
// 5. YAML parse -> graph: known types processed via generic path
// ===========================================================================

describe("Parse from YAML: known types via generic path", () => {
  it("linear block parses soul_ref -> soulRef via generic conversion", () => {
    const yaml = makeYaml({
      step1: { type: "linear", soul_ref: "analyst" },
    });
    const result = parseWorkflowYamlToGraph(yaml);
    expect(result.nodes[0]!.data.soulRef).toBe("analyst");
  });

  it("loop block parses carry_context with recursive key conversion", () => {
    const yaml = makeYaml({
      step1: {
        type: "loop",
        inner_block_refs: ["step_a"],
        max_rounds: 5,
        carry_context: {
          enabled: true,
          source_blocks: ["step_a"],
          inject_as: "prior",
        },
      },
    });
    const result = parseWorkflowYamlToGraph(yaml);
    const data = result.nodes[0]!.data;

    expect(data.innerBlockRefs).toEqual(["step_a"]);
    expect(data.maxRounds).toBe(5);
    // carry_context should have recursively-converted keys
    const cc = data.carryContext as Record<string, unknown>;
    expect(cc.enabled).toBe(true);
    expect(cc.sourceBlocks).toEqual(["step_a"]);
    expect(cc.injectAs).toBe("prior");
  });

  it("http_request block parses all snake_case fields to camelCase", () => {
    const yaml = makeYaml({
      step1: {
        type: "http_request",
        url: "https://example.com",
        method: "POST",
        body_type: "json",
        auth_type: "bearer",
        auth_config: { token_env: "API_TOKEN" },
        timeout_seconds: 30,
        retry_count: 2,
        retry_backoff: "fixed",
        expected_status_codes: [200],
        allow_private_ips: false,
      },
    });
    const result = parseWorkflowYamlToGraph(yaml);
    const data = result.nodes[0]!.data;

    expect(data.url).toBe("https://example.com");
    expect(data.method).toBe("POST");
    expect(data.bodyType).toBe("json");
    expect(data.authType).toBe("bearer");
    expect(data.timeoutSeconds).toBe(30);
    expect(data.retryCount).toBe(2);
    expect(data.retryBackoff).toBe("fixed");
    expect(data.expectedStatusCodes).toEqual([200]);
    expect(data.allowPrivateIps).toBe(false);
    // nested auth_config keys should be converted
    const ac = data.authConfig as Record<string, unknown>;
    expect(ac.tokenEnv).toBe("API_TOKEN");
  });
});
