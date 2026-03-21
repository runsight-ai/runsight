/**
 * RED-TEAM tests for RUN-221: Generic Block Round-Trip.
 *
 * The frontend must accept ANY block type string and round-trip ALL fields
 * faithfully -- including types it has never seen before. After this ticket,
 * adding a new block type on the backend requires ZERO frontend code changes.
 *
 * These tests MUST FAIL until the Green Team implements:
 *  - Parser: accept any string as a valid block type (no VALID_STEP_TYPES rejection)
 *  - Parser: generic snake_case -> camelCase field mapping for unknown fields
 *  - Compiler: generic camelCase -> snake_case field emission for unknown types
 *
 * Failure reasons against current implementation:
 *  - `toStepType()` falls back to "linear" for unknown types
 *  - `buildNodeData()` only maps fields via explicit if-chains
 *  - `toCompiledBlock()` only emits fields listed in BLOCK_TYPE_FIELDS
 */

import { describe, it, expect } from "vitest";
import { dump } from "js-yaml";
import { parseWorkflowYamlToGraph } from "../yamlParser";
import { compileGraphToWorkflowYaml } from "../yamlCompiler";
import type { StepNodeData, StepType, SoulDef } from "../../../types/schemas/canvas";
import type { Node, Edge } from "@xyflow/react";

// ---------------------------------------------------------------------------
// Helpers (following existing patterns from yamlParser.test.ts & yamlCompiler.test.ts)
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
  return result.nodes[0]!.data;
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

interface CompileInput {
  nodes: Node<StepNodeData>[];
  edges: Edge[];
  workflowName?: string;
  souls?: Record<string, SoulDef>;
  config?: Record<string, unknown>;
}

/** Convenience to access block from compiled doc as a plain record. */
function getBlock(doc: { blocks: Record<string, unknown> }, id: string): Record<string, unknown> {
  return doc.blocks[id] as Record<string, unknown>;
}

function compileOne(node: Node<StepNodeData>) {
  const result = compileGraphToWorkflowYaml({ nodes: [node], edges: [] });
  return {
    block: getBlock(result.workflowDocument, node.id),
    yaml: result.yaml,
    doc: result.workflowDocument,
  };
}

/** Core round-trip: compile -> parse -> compile. */
function roundTrip(input: CompileInput) {
  const { yaml: yaml1, workflowDocument: doc1 } = compileGraphToWorkflowYaml(input);
  const parsed = parseWorkflowYamlToGraph(yaml1);

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
// 1. Parser accepts unknown block types
// ===========================================================================

describe("Parser: unknown block type accepted", () => {
  it("accepts 'custom_thing' as a valid block type (no fallback to linear)", () => {
    const yaml = makeYaml({
      step1: { type: "custom_thing", foo_bar: 42, baz_qux: "hello" },
    });
    const data = parseFirst(yaml);

    // FAILS: toStepType() falls back to "linear" for unknown types
    expect(data.stepType).toBe("custom_thing");
  });

  it("does not produce a parse error for unknown block types", () => {
    const yaml = makeYaml({
      step1: { type: "custom_thing", foo_bar: 42 },
    });
    const result = parseWorkflowYamlToGraph(yaml);

    // FAILS: toStepType() returns an error for unknown types
    expect(result.error).toBeUndefined();
  });

  it("accepts 'data_transform' as a valid block type", () => {
    const yaml = makeYaml({
      step1: { type: "data_transform", transform_fn: "normalize", chunk_size: 100 },
    });
    const data = parseFirst(yaml);

    expect(data.stepType).toBe("data_transform");
  });

  it("accepts a single-word unknown type like 'custom'", () => {
    const yaml = makeYaml({
      step1: { type: "custom", alpha: 1 },
    });
    const data = parseFirst(yaml);

    expect(data.stepType).toBe("custom");
  });
});

// ===========================================================================
// 2. Parser: generic snake_case -> camelCase field mapping
// ===========================================================================

describe("Parser: unknown fields mapped snake_case -> camelCase", () => {
  it("maps foo_bar -> fooBar and baz_qux -> bazQux for custom_thing type", () => {
    const yaml = makeYaml({
      step1: { type: "custom_thing", foo_bar: 42, baz_qux: "hello" },
    });
    const data = parseFirst(yaml);

    // FAILS: buildNodeData() only maps known fields via explicit if-chains
    expect(data.stepType).toBe("custom_thing");
    expect((data as Record<string, unknown>).fooBar).toBe(42);
    expect((data as Record<string, unknown>).bazQux).toBe("hello");
  });

  it("maps deeply_nested_field -> deeplyNestedField for unknown types", () => {
    const yaml = makeYaml({
      step1: {
        type: "data_transform",
        transform_fn: "normalize",
        max_batch_size: 500,
        enable_parallel_processing: true,
      },
    });
    const data = parseFirst(yaml);

    expect(data.stepType).toBe("data_transform");
    expect((data as Record<string, unknown>).transformFn).toBe("normalize");
    expect((data as Record<string, unknown>).maxBatchSize).toBe(500);
    expect((data as Record<string, unknown>).enableParallelProcessing).toBe(true);
  });

  it("handles nested object fields with recursive key conversion", () => {
    const yaml = makeYaml({
      step1: {
        type: "custom_thing",
        nested_config: {
          inner_key: "value",
          deep_nested: {
            leaf_value: 99,
          },
        },
      },
    });
    const data = parseFirst(yaml);

    expect(data.stepType).toBe("custom_thing");
    const nestedConfig = (data as Record<string, unknown>).nestedConfig as Record<string, unknown>;
    expect(nestedConfig).toBeDefined();
    expect(nestedConfig.innerKey).toBe("value");
    expect((nestedConfig.deepNested as Record<string, unknown>).leafValue).toBe(99);
  });

  it("handles array field values correctly", () => {
    const yaml = makeYaml({
      step1: {
        type: "custom_thing",
        item_list: ["alpha", "beta", "gamma"],
        tag_ids: [1, 2, 3],
      },
    });
    const data = parseFirst(yaml);

    expect((data as Record<string, unknown>).itemList).toEqual(["alpha", "beta", "gamma"]);
    expect((data as Record<string, unknown>).tagIds).toEqual([1, 2, 3]);
  });

  it("does not set undefined/null fields as keys (no pollution)", () => {
    const yaml = makeYaml({
      step1: { type: "custom_thing", foo_bar: 42 },
    });
    const data = parseFirst(yaml);
    const keys = Object.keys(data);

    // Only expected keys: stepId, name, stepType, status, fooBar
    expect(keys).toContain("fooBar");
    expect(keys).not.toContain("bazQux"); // was never in YAML
  });

  it("fields already in camelCase in YAML are preserved as-is (defensive)", () => {
    const yaml = makeYaml({
      step1: { type: "custom_thing", alreadyCamel: "preserved" },
    });
    const data = parseFirst(yaml);

    // A field already in camelCase should pass through unchanged
    expect((data as Record<string, unknown>).alreadyCamel).toBe("preserved");
  });
});

// ===========================================================================
// 3. Compiler: unknown block type and fields emitted
// ===========================================================================

describe("Compiler: unknown block type emits all fields", () => {
  it("emits type: custom_thing with foo_bar and baz_qux in snake_case", () => {
    const node = mockNode("step1", "custom_thing", {
      fooBar: 42,
      bazQux: "hello",
    } as unknown as Partial<StepNodeData>);

    const { block } = compileOne(node);

    // FAILS: BLOCK_TYPE_FIELDS lookup returns undefined for "custom_thing"
    expect(block.type).toBe("custom_thing");
    expect(block.foo_bar).toBe(42);
    expect(block.baz_qux).toBe("hello");
  });

  it("emits snake_case keys in YAML string for unknown types", () => {
    const node = mockNode("step1", "custom_thing", {
      fooBar: 42,
      bazQux: "hello",
    } as unknown as Partial<StepNodeData>);

    const { yaml } = compileOne(node);

    expect(yaml).toContain("type: custom_thing");
    expect(yaml).toContain("foo_bar: 42");
    expect(yaml).toContain("baz_qux: hello");
    expect(yaml).not.toContain("fooBar:");
    expect(yaml).not.toContain("bazQux:");
  });

  it("omits runtime fields (status, cost, name, stepId) from unknown block compilation", () => {
    const node = mockNode("step1", "custom_thing", {
      fooBar: 42,
      cost: 0.05,
      executionCost: 0.12,
    } as unknown as Partial<StepNodeData>);

    const { block } = compileOne(node);

    expect(block).not.toHaveProperty("status");
    expect(block).not.toHaveProperty("cost");
    expect(block).not.toHaveProperty("execution_cost");
    expect(block).not.toHaveProperty("name");
    expect(block).not.toHaveProperty("step_id");
  });

  it("omits undefined/null values from unknown block compilation", () => {
    const node = mockNode("step1", "custom_thing", {
      fooBar: 42,
      nullField: null,
      undefField: undefined,
    } as unknown as Partial<StepNodeData>);

    const { block } = compileOne(node);

    expect(block.foo_bar).toBe(42);
    expect(block).not.toHaveProperty("null_field");
    expect(block).not.toHaveProperty("undef_field");
  });

  it("handles nested object fields with recursive camelCase -> snake_case", () => {
    const node = mockNode("step1", "custom_thing", {
      nestedConfig: {
        innerKey: "value",
        deepNested: {
          leafValue: 99,
        },
      },
    } as unknown as Partial<StepNodeData>);

    const { block } = compileOne(node);
    const nestedConfig = block.nested_config as Record<string, unknown>;

    expect(nestedConfig).toBeDefined();
    expect(nestedConfig.inner_key).toBe("value");
    expect((nestedConfig.deep_nested as Record<string, unknown>).leaf_value).toBe(99);
  });

  it("emits universal fields (output_conditions, retry_config) on unknown types", () => {
    const node = mockNode("step1", "custom_thing", {
      fooBar: 42,
      outputConditions: [{ case_id: "done", default: true }],
      retryConfig: { maxAttempts: 3, backoff: "exponential" },
    } as unknown as Partial<StepNodeData>);

    const { block } = compileOne(node);

    expect(block.type).toBe("custom_thing");
    expect(block.foo_bar).toBe(42);
    expect(block.output_conditions).toBeDefined();
    expect(block.retry_config).toBeDefined();
    expect((block.retry_config as Record<string, unknown>).max_attempts).toBe(3);
  });
});

// ===========================================================================
// 4. Full round-trip: parse -> compile -> parse produces identical structure
// ===========================================================================

describe("Full round-trip: custom_thing block", () => {
  it("custom_thing with foo_bar: 42, baz_qux: 'hello' round-trips losslessly", () => {
    const node = mockNode("step1", "custom_thing", {
      fooBar: 42,
      bazQux: "hello",
    } as unknown as Partial<StepNodeData>);

    const { doc1, doc2, yaml1, yaml2 } = roundTrip({ nodes: [node], edges: [] });

    const block1 = getBlock(doc1, "step1");
    const block2 = getBlock(doc2, "step1");

    // FAILS: type falls back to "linear", fields are lost
    expect(block1.type).toBe("custom_thing");
    expect(block1.foo_bar).toBe(42);
    expect(block1.baz_qux).toBe("hello");

    // Round-trip equality
    expect(block2).toEqual(block1);
    expect(yaml2).toBe(yaml1);
  });

  it("parse -> compile round-trip: YAML with unknown type produces same YAML", () => {
    const yamlInput = makeYaml({
      step1: { type: "custom_thing", foo_bar: 42, baz_qux: "hello" },
    });

    // Parse YAML to graph
    const parsed = parseWorkflowYamlToGraph(yamlInput);
    expect(parsed.error).toBeUndefined();
    expect(parsed.nodes).toHaveLength(1);
    expect(parsed.nodes[0]!.data.stepType).toBe("custom_thing");

    // Compile graph back to YAML
    const compiled = compileGraphToWorkflowYaml({
      nodes: parsed.nodes,
      edges: parsed.edges,
      workflowName: "test",
    });

    const block = getBlock(compiled.workflowDocument, "step1");
    expect(block.type).toBe("custom_thing");
    expect(block.foo_bar).toBe(42);
    expect(block.baz_qux).toBe("hello");
  });
});

// ===========================================================================
// 5. Mixed known + unknown types in same workflow
// ===========================================================================

describe("Mixed known + unknown types round-trip", () => {
  it("workflow with linear, http_request, and custom_thing all round-trip correctly", () => {
    const souls: Record<string, SoulDef> = {
      planner: {
        id: "planner",
        role: "planner",
        system_prompt: "You plan tasks.",
        model_name: "claude-3-opus",
      },
    };

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

    const { doc1, doc2, yaml1, yaml2 } = roundTrip({ nodes, edges, souls });

    // Known types should still work
    const planBlock = getBlock(doc1, "plan");
    expect(planBlock.type).toBe("linear");
    expect(planBlock.soul_ref).toBe("planner");

    const fetchBlock = getBlock(doc1, "fetch");
    expect(fetchBlock.type).toBe("http_request");
    expect(fetchBlock.url).toBe("https://api.example.com/data");

    // Unknown type should also work
    const transformBlock = getBlock(doc1, "transform");
    expect(transformBlock.type).toBe("custom_thing");
    expect(transformBlock.foo_bar).toBe(42);
    expect(transformBlock.baz_qux).toBe("hello");

    // Full round-trip equality
    expect(doc2.blocks).toEqual(doc1.blocks);
    expect(doc2.workflow.transitions).toEqual(doc1.workflow.transitions);
    expect(yaml2).toBe(yaml1);
  });

  it("workflow with multiple unknown types round-trips correctly", () => {
    const nodes = [
      mockNode("step1", "data_transform", {
        transformFn: "normalize",
        chunkSize: 100,
      } as unknown as Partial<StepNodeData>),
      mockNode("step2", "ai_validator", {
        modelRef: "gpt-4",
        validationRules: ["not_empty", "is_json"],
      } as unknown as Partial<StepNodeData>),
      mockNode("step3", "webhook_sender", {
        webhookUrl: "https://hooks.example.com/notify",
        payloadTemplate: '{"status": "done"}',
      } as unknown as Partial<StepNodeData>),
    ];

    const edges = [
      mockEdge("step1", "step2"),
      mockEdge("step2", "step3"),
    ];

    const { doc1, doc2, yaml1, yaml2 } = roundTrip({ nodes, edges });

    // All unknown types must survive
    expect(getBlock(doc1, "step1").type).toBe("data_transform");
    expect(getBlock(doc1, "step2").type).toBe("ai_validator");
    expect(getBlock(doc1, "step3").type).toBe("webhook_sender");

    // All fields must survive
    expect(getBlock(doc1, "step1").transform_fn).toBe("normalize");
    expect(getBlock(doc1, "step2").model_ref).toBe("gpt-4");
    expect(getBlock(doc1, "step3").webhook_url).toBe("https://hooks.example.com/notify");

    expect(doc2.blocks).toEqual(doc1.blocks);
    expect(yaml2).toBe(yaml1);
  });
});

// ===========================================================================
// 6. Empty block (just type) round-trips
// ===========================================================================

describe("Empty block round-trip", () => {
  it("block with only type: 'empty_block' round-trips as { type: 'empty_block' }", () => {
    const node = mockNode("step1", "empty_block");

    const { doc1, doc2 } = roundTrip({ nodes: [node], edges: [] });

    const block1 = getBlock(doc1, "step1");
    // FAILS: type falls back to "linear"
    expect(block1).toEqual({ type: "empty_block" });
    expect(doc2.blocks["step1"]).toEqual(doc1.blocks["step1"]);
  });

  it("empty unknown block parsed from YAML has only base fields on node data", () => {
    const yaml = makeYaml({
      step1: { type: "empty_block" },
    });
    const data = parseFirst(yaml);
    const keys = Object.keys(data);

    expect(data.stepType).toBe("empty_block");
    // Should only have stepId, name, stepType, status
    expect(keys).toContain("stepId");
    expect(keys).toContain("name");
    expect(keys).toContain("stepType");
    expect(keys).toContain("status");
    expect(keys).toHaveLength(4);
  });
});

// ===========================================================================
// 7. Nested objects get key conversion for unknown types
// ===========================================================================

describe("Nested objects: key conversion on unknown types", () => {
  it("deeply nested object keys are converted snake_case -> camelCase on parse", () => {
    const yaml = makeYaml({
      step1: {
        type: "custom_thing",
        complex_config: {
          first_level: {
            second_level: {
              third_level_value: "deep",
            },
            array_of_objects: [
              { item_name: "one", item_count: 1 },
              { item_name: "two", item_count: 2 },
            ],
          },
        },
      },
    });
    const data = parseFirst(yaml);

    const complexConfig = (data as Record<string, unknown>).complexConfig as Record<string, unknown>;
    expect(complexConfig).toBeDefined();

    const firstLevel = complexConfig.firstLevel as Record<string, unknown>;
    expect(firstLevel).toBeDefined();

    const secondLevel = firstLevel.secondLevel as Record<string, unknown>;
    expect(secondLevel.thirdLevelValue).toBe("deep");

    const arrayOfObjects = firstLevel.arrayOfObjects as Array<Record<string, unknown>>;
    expect(arrayOfObjects).toHaveLength(2);
    expect(arrayOfObjects[0]!.itemName).toBe("one");
    expect(arrayOfObjects[0]!.itemCount).toBe(1);
  });

  it("deeply nested object keys are converted camelCase -> snake_case on compile", () => {
    const node = mockNode("step1", "custom_thing", {
      complexConfig: {
        firstLevel: {
          secondLevel: {
            thirdLevelValue: "deep",
          },
          arrayOfObjects: [
            { itemName: "one", itemCount: 1 },
            { itemName: "two", itemCount: 2 },
          ],
        },
      },
    } as unknown as Partial<StepNodeData>);

    const { block } = compileOne(node);

    const complexConfig = block.complex_config as Record<string, unknown>;
    expect(complexConfig).toBeDefined();

    const firstLevel = complexConfig.first_level as Record<string, unknown>;
    expect(firstLevel).toBeDefined();

    const secondLevel = firstLevel.second_level as Record<string, unknown>;
    expect(secondLevel.third_level_value).toBe("deep");

    const arrayOfObjects = firstLevel.array_of_objects as Array<Record<string, unknown>>;
    expect(arrayOfObjects).toHaveLength(2);
    expect(arrayOfObjects[0]!.item_name).toBe("one");
    expect(arrayOfObjects[0]!.item_count).toBe(1);
  });
});

// ===========================================================================
// 8. Workflow special case still works after generic changes
// ===========================================================================

describe("Workflow special case preserved", () => {
  it("workflow block inputs/outputs still remap to workflowInputs/workflowOutputs on parse", () => {
    const yaml = makeYaml({
      sub: {
        type: "workflow",
        workflow_ref: "sub.yaml",
        max_depth: 3,
        inputs: { query: "parent.user_query" },
        outputs: { summary: "child.result.summary" },
      },
    });
    const data = parseFirst(yaml);

    expect(data.stepType).toBe("workflow");
    expect(data.workflowRef).toBe("sub.yaml");
    expect(data.maxDepth).toBe(3);
    // Workflow block: inputs -> workflowInputs, outputs -> workflowOutputs
    expect(data.workflowInputs).toEqual({ query: "parent.user_query" });
    expect(data.workflowOutputs).toEqual({ summary: "child.result.summary" });
    // Should NOT have generic inputs/outputs
    expect(data.inputs).toBeUndefined();
    expect(data.outputs).toBeUndefined();
  });

  it("workflow block workflowInputs/workflowOutputs compile back to inputs/outputs", () => {
    const node = mockNode("sub", "workflow", {
      workflowRef: "sub.yaml",
      maxDepth: 3,
      workflowInputs: { query: "parent.user_query" },
      workflowOutputs: { summary: "child.result.summary" },
    });

    const { block } = compileOne(node);

    expect(block.type).toBe("workflow");
    expect(block.workflow_ref).toBe("sub.yaml");
    expect(block.max_depth).toBe(3);
    expect(block.inputs).toEqual({ query: "parent.user_query" });
    expect(block.outputs).toEqual({ summary: "child.result.summary" });
  });

  it("workflow block round-trips with inputs/outputs correctly", () => {
    const node = mockNode("sub", "workflow", {
      workflowRef: "sub.yaml",
      maxDepth: 3,
      workflowInputs: { query: "parent.user_query" },
      workflowOutputs: { summary: "child.result.summary" },
    });

    const { doc1, doc2, yaml1, yaml2 } = roundTrip({ nodes: [node], edges: [] });

    expect(doc2.blocks["sub"]).toEqual(doc1.blocks["sub"]);
    expect(yaml2).toBe(yaml1);
  });
});

// ===========================================================================
// 9. Known type fields still work (carry_context, retry_config, break_condition)
// ===========================================================================

describe("Known nested object fields still work after generic changes", () => {
  it("carry_context still gets key conversion on parse", () => {
    const yaml = makeYaml({
      step1: {
        type: "loop",
        inner_block_refs: ["step_a"],
        carry_context: {
          enabled: true,
          mode: "last",
          source_blocks: ["step_a"],
          inject_as: "previous_output",
        },
      },
    });
    const data = parseFirst(yaml);

    expect(data.carryContext).toEqual({
      enabled: true,
      mode: "last",
      sourceBlocks: ["step_a"],
      injectAs: "previous_output",
    });
  });

  it("retry_config still gets key conversion on parse", () => {
    const yaml = makeYaml({
      step1: {
        type: "linear",
        soul_ref: "analyst",
        retry_config: {
          max_attempts: 3,
          backoff: "exponential",
          backoff_base_seconds: 2,
        },
      },
    });
    const data = parseFirst(yaml);

    expect(data.retryConfig).toEqual({
      maxAttempts: 3,
      backoff: "exponential",
      backoffBaseSeconds: 2,
    });
  });

  it("carry_context still gets key conversion on compile", () => {
    const node = mockNode("step1", "loop", {
      innerBlockRefs: ["step_a"],
      carryContext: {
        enabled: true,
        mode: "last",
        sourceBlocks: ["step_a"],
        injectAs: "previous_output",
      },
    });

    const { block } = compileOne(node);

    expect(block.carry_context).toEqual({
      enabled: true,
      mode: "last",
      source_blocks: ["step_a"],
      inject_as: "previous_output",
    });
  });

  it("loop with break_condition round-trips correctly", () => {
    const node = mockNode("step1", "loop", {
      innerBlockRefs: ["step_a", "step_b"],
      maxRounds: 5,
      breakCondition: "result.converged == true",
    });

    const { doc1, doc2 } = roundTrip({ nodes: [node], edges: [] });

    expect(doc2.blocks["step1"]).toEqual(doc1.blocks["step1"]);
  });
});

// ===========================================================================
// 10. Existing known types are not broken
// ===========================================================================

describe("Existing known types unaffected by generic changes", () => {
  it("linear block still round-trips", () => {
    const node = mockNode("b1", "linear", { soulRef: "analyst" });
    const { doc1, doc2 } = roundTrip({ nodes: [node], edges: [] });
    expect(doc2.blocks["b1"]).toEqual(doc1.blocks["b1"]);
  });

  it("code block still round-trips", () => {
    const node = mockNode("b1", "code", {
      code: "print('hello')",
      timeoutSeconds: 60,
      allowedImports: ["json", "math"],
    });
    const { doc1, doc2 } = roundTrip({ nodes: [node], edges: [] });
    expect(doc2.blocks["b1"]).toEqual(doc1.blocks["b1"]);
  });

  it("loop block still round-trips", () => {
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
    expect(doc2.blocks["b1"]).toEqual(doc1.blocks["b1"]);
  });

  it("gate block still round-trips", () => {
    const node = mockNode("b1", "gate", {
      soulRef: "gatekeeper",
      evalKey: "quality",
      extractField: "score",
    });
    const { doc1, doc2 } = roundTrip({ nodes: [node], edges: [] });
    expect(doc2.blocks["b1"]).toEqual(doc1.blocks["b1"]);
  });

  it("http_request block still round-trips", () => {
    const node = mockNode("b1", "http_request", {
      url: "https://api.example.com",
      method: "POST",
      bodyType: "json",
      timeoutSeconds: 30,
      expectedStatusCodes: [200, 201],
    });
    const { doc1, doc2 } = roundTrip({ nodes: [node], edges: [] });
    expect(doc2.blocks["b1"]).toEqual(doc1.blocks["b1"]);
  });
});
