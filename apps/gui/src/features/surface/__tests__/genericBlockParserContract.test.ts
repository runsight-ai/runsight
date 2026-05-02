import { describe, expect, it } from "vitest";

import { parseWorkflowYamlToGraph } from "../yamlParser";
import { makeYaml, parseFirst } from "./helpers/genericBlockRoundTripHelpers";

describe("Parser: unknown block type accepted", () => {
  it("accepts 'custom_thing' as a valid block type (no fallback to linear)", () => {
    const yaml = makeYaml({
      step1: { type: "custom_thing", foo_bar: 42, baz_qux: "hello" },
    });
    const data = parseFirst(yaml);

    expect(data.stepType).toBe("custom_thing");
  });

  it("does not produce a parse error for unknown block types", () => {
    const yaml = makeYaml({
      step1: { type: "custom_thing", foo_bar: 42 },
    });
    const result = parseWorkflowYamlToGraph(yaml);

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

describe("Parser: unknown fields mapped snake_case -> camelCase", () => {
  it("maps foo_bar -> fooBar and baz_qux -> bazQux for custom_thing type", () => {
    const yaml = makeYaml({
      step1: { type: "custom_thing", foo_bar: 42, baz_qux: "hello" },
    });
    const data = parseFirst(yaml);

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

    expect(keys).toContain("fooBar");
    expect(keys).not.toContain("bazQux");
  });

  it("fields already in camelCase in YAML are preserved as-is (defensive)", () => {
    const yaml = makeYaml({
      step1: { type: "custom_thing", alreadyCamel: "preserved" },
    });
    const data = parseFirst(yaml);

    expect((data as Record<string, unknown>).alreadyCamel).toBe("preserved");
  });
});

describe("Parser: known nested fields still use canonical key conversion", () => {
  it("maps loop carry_context to carryContext", () => {
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

  it("maps retry_config to retryConfig", () => {
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
});
