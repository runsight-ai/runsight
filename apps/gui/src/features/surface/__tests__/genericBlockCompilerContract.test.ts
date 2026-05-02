import { describe, expect, it } from "vitest";

import type { StepNodeData } from "../../../types/schemas/canvas";
import { compileOne, mockNode } from "./helpers/genericBlockRoundTripHelpers";

describe("Compiler: unknown block type emits all fields", () => {
  it("emits type: custom_thing with foo_bar and baz_qux in snake_case", () => {
    const node = mockNode("step1", "custom_thing", {
      fooBar: 42,
      bazQux: "hello",
    } as unknown as Partial<StepNodeData>);

    const { block } = compileOne(node);

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

describe("Compiler: known nested fields keep canonical YAML keys", () => {
  it("emits carry_context with snake_case child keys", () => {
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
});
