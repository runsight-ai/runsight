import { describe, expect, it } from "vitest";
import {
  compileOne,
  mockNode,
  sampleOutputConditions,
} from "./helpers/yamlCompilerFixtures";

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
