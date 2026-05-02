import { describe, expect, it } from "vitest";

import { compileGraphToWorkflowYaml } from "../yamlCompiler";
import { parseWorkflowYamlToGraph } from "../yamlParser";
import type { StepNodeData } from "../../../types/schemas/canvas";
import {
  compileOne,
  getBlock,
  makeYaml,
  mockEdge,
  mockNode,
  parseFirst,
  roundTrip,
} from "./helpers/genericBlockRoundTripHelpers";

describe("Full round-trip: custom_thing block", () => {
  it("custom_thing with foo_bar: 42, baz_qux: 'hello' round-trips losslessly", () => {
    const node = mockNode("step1", "custom_thing", {
      fooBar: 42,
      bazQux: "hello",
    } as unknown as Partial<StepNodeData>);

    const { doc1, doc2, yaml1, yaml2 } = roundTrip({ nodes: [node], edges: [] });

    const block1 = getBlock(doc1, "step1");
    const block2 = getBlock(doc2, "step1");

    expect(block1.type).toBe("custom_thing");
    expect(block1.foo_bar).toBe(42);
    expect(block1.baz_qux).toBe("hello");
    expect(block2).toEqual(block1);
    expect(yaml2).toBe(yaml1);
  });

  it("parse -> compile round-trip: YAML with unknown type produces same block shape", () => {
    const yamlInput = makeYaml({
      step1: { type: "custom_thing", foo_bar: 42, baz_qux: "hello" },
    });

    const parsed = parseWorkflowYamlToGraph(yamlInput);
    expect(parsed.error).toBeUndefined();
    expect(parsed.nodes).toHaveLength(1);
    expect(parsed.nodes[0]!.data.stepType).toBe("custom_thing");

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

describe("Mixed known + unknown types round-trip", () => {
  it("workflow with linear, http_request, and custom_thing all round-trip correctly", () => {
    const nodes = [
      mockNode("plan", "linear", { soulRef: "planner" }),
      mockNode("transform", "custom_thing", {
        fooBar: 42,
        bazQux: "hello",
      } as unknown as Partial<StepNodeData>),
      mockNode("fetch", "http_request", {
        url: "https://api.example.test/data",
        method: "GET",
        timeoutSeconds: 15,
      }),
    ];

    const edges = [
      mockEdge("plan", "transform"),
      mockEdge("transform", "fetch"),
    ];

    const { doc1, doc2, yaml1, yaml2 } = roundTrip({ nodes, edges });

    const planBlock = getBlock(doc1, "plan");
    expect(planBlock.type).toBe("linear");
    expect(planBlock.soul_ref).toBe("planner");

    const fetchBlock = getBlock(doc1, "fetch");
    expect(fetchBlock.type).toBe("http_request");
    expect(fetchBlock.url).toBe("https://api.example.test/data");

    const transformBlock = getBlock(doc1, "transform");
    expect(transformBlock.type).toBe("custom_thing");
    expect(transformBlock.foo_bar).toBe(42);
    expect(transformBlock.baz_qux).toBe("hello");

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
        webhookUrl: "https://hooks.example.test/notify",
        payloadTemplate: '{"status": "done"}',
      } as unknown as Partial<StepNodeData>),
    ];

    const edges = [
      mockEdge("step1", "step2"),
      mockEdge("step2", "step3"),
    ];

    const { doc1, doc2, yaml1, yaml2 } = roundTrip({ nodes, edges });

    expect(getBlock(doc1, "step1").type).toBe("data_transform");
    expect(getBlock(doc1, "step2").type).toBe("ai_validator");
    expect(getBlock(doc1, "step3").type).toBe("webhook_sender");
    expect(getBlock(doc1, "step1").transform_fn).toBe("normalize");
    expect(getBlock(doc1, "step2").model_ref).toBe("gpt-4");
    expect(getBlock(doc1, "step3").webhook_url).toBe("https://hooks.example.test/notify");

    expect(doc2.blocks).toEqual(doc1.blocks);
    expect(yaml2).toBe(yaml1);
  });
});

describe("Empty block round-trip", () => {
  it("block with only type: 'empty_block' round-trips as { type: 'empty_block' }", () => {
    const node = mockNode("step1", "empty_block");

    const { doc1, doc2 } = roundTrip({ nodes: [node], edges: [] });

    const block1 = getBlock(doc1, "step1");
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
    expect(keys).toContain("stepId");
    expect(keys).toContain("name");
    expect(keys).toContain("stepType");
    expect(keys).toContain("status");
    expect(keys).toHaveLength(4);
  });
});

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
