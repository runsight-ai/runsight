import { describe, expect, it } from "vitest";
import {
  compileOne,
  mockNode,
  sampleOutputConditions,
} from "./helpers/yamlCompilerFixtures";

describe("Per-type block field emission", () => {
  it("linear: emits soul_ref", () => {
    const { block } = compileOne(
      mockNode("b1", "linear", { soulRef: "planner_soul" }),
    );
    expect(block.type).toBe("linear");
    expect(block).toHaveProperty("soul_ref", "planner_soul");
  });

  it("dispatch: emits soul_refs array", () => {
    const { block } = compileOne(
      mockNode("b1", "dispatch", { soulRefs: ["s1", "s2", "s3"] }),
    );
    expect(block.type).toBe("dispatch");
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

  it("dispatch: emits soul_ref", () => {
    const { block } = compileOne(
      mockNode("b1", "dispatch", {
        soulRef: "dispatch_soul",
      }),
    );
    expect(block.type).toBe("dispatch");
    expect(block).toHaveProperty("soul_ref", "dispatch_soul");
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

  it("loop: emits inner_block_refs, max_rounds, break_condition, carry_context", () => {
    const { block } = compileOne(
      mockNode("b1", "loop", {
        innerBlockRefs: ["step_a", "step_b"],
        maxRounds: 5,
        breakCondition: "result.converged == true",
        carryContext: {
          enabled: true,
          mode: "last",
          sourceBlocks: ["step_b"],
          injectAs: "previous_output",
        },
      }),
    );
    expect(block.type).toBe("loop");
    expect(block).toHaveProperty("inner_block_refs", ["step_a", "step_b"]);
    expect(block).toHaveProperty("max_rounds", 5);
    expect(block).toHaveProperty("break_condition", "result.converged == true");
    expect(block).toHaveProperty("carry_context");
    expect((block as Record<string, unknown>).carry_context).toEqual({
      enabled: true,
      mode: "last",
      source_blocks: ["step_b"],
      inject_as: "previous_output",
    });
  });

  it("loop: emits minimal loop with only inner_block_refs", () => {
    const { block } = compileOne(
      mockNode("b1", "loop", {
        innerBlockRefs: ["single_block"],
      }),
    );
    expect(block.type).toBe("loop");
    expect(block).toHaveProperty("inner_block_refs", ["single_block"]);
    expect(block).not.toHaveProperty("max_rounds");
    expect(block).not.toHaveProperty("break_condition");
    expect(block).not.toHaveProperty("carry_context");
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

describe("Generic path emits all non-runtime fields", () => {
  it("linear node with extra fields emits them via generic path", () => {
    const { block } = compileOne(
      mockNode("b1", "linear", {
        soulRef: "soul1",
        iterations: 5,
      }),
    );
    // Generic path emits all non-runtime fields
    expect(block).toHaveProperty("soul_ref", "soul1");
    expect(block).toHaveProperty("iterations", 5);
  });

  it("code node with soulRef set emits soul_ref via generic path", () => {
    const { block } = compileOne(
      mockNode("b1", "code", {
        code: "x=1",
        soulRef: "some_soul",
      }),
    );
    // Generic path converts camelCase to snake_case for all fields
    expect(block).toHaveProperty("soul_ref", "some_soul");
  });

  it("gate node emits all fields via generic path", () => {
    const { block } = compileOne(
      mockNode("b1", "gate", {
        soulRef: "gate_soul",
        evalKey: "result.ok",
        iterations: 3,
        innerBlockRefs: ["x"],
      }),
    );
    expect(block).toHaveProperty("iterations", 3);
    expect(block).toHaveProperty("inner_block_refs");
  });

  it("dispatch node emits soul_ref alongside soul_refs via generic path", () => {
    const { block } = compileOne(
      mockNode("b1", "dispatch", {
        soulRefs: ["s1"],
        soulRef: "extra_soul",
      }),
    );
    expect(block).toHaveProperty("soul_ref", "extra_soul");
    expect(block).toHaveProperty("soul_refs");
  });

  it("code node emits all extra fields via generic path", () => {
    const { block } = compileOne(
      mockNode("b1", "code", {
        code: "x = 1",
        soulRef: "nope",
        iterations: 10,
      }),
    );
    expect(block).toHaveProperty("soul_ref", "nope");
    expect(block).toHaveProperty("iterations", 10);
  });

  it("file_writer node emits all fields via generic path", () => {
    const { block } = compileOne(
      mockNode("b1", "file_writer", {
        outputPath: "/out.txt",
        contentKey: "data",
        code: "some_code",
        soulRef: "extra",
      }),
    );
    expect(block).toHaveProperty("code", "some_code");
    expect(block).toHaveProperty("soul_ref", "extra");
  });
});

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

  it("outputs are emitted on a linear block", () => {
    const { block } = compileOne(
      mockNode("b1", "linear", {
        soulRef: "a",
        outputs: { winner: "string" },
      }),
    );
    expect(block).toHaveProperty("outputs");
    expect(block.outputs).toEqual({ winner: "string" });
  });

  it("output_conditions are emitted on a file_writer block", () => {
    const { block } = compileOne(
      mockNode("b1", "file_writer", {
        outputPath: "/out.txt",
        outputConditions: sampleOutputConditions,
      }),
    );
    expect(block).toHaveProperty("output_conditions");
  });

  it("retryConfig is emitted as retry_config on a linear block", () => {
    const { block } = compileOne(
      mockNode("b1", "linear", {
        soulRef: "soul1",
        retryConfig: {
          maxAttempts: 3,
          backoff: "exponential",
          backoffBaseSeconds: 2,
          nonRetryableErrors: ["AuthError"],
        },
      }),
    );
    expect(block).toHaveProperty("retry_config");
    expect((block as Record<string, unknown>).retry_config).toEqual({
      max_attempts: 3,
      backoff: "exponential",
      backoff_base_seconds: 2,
      non_retryable_errors: ["AuthError"],
    });
  });

  it("retryConfig is emitted as retry_config on a loop block", () => {
    const { block } = compileOne(
      mockNode("b1", "loop", {
        innerBlockRefs: ["step_a"],
        maxRounds: 3,
        retryConfig: {
          maxAttempts: 2,
          backoff: "fixed",
          backoffBaseSeconds: 5,
        },
      }),
    );
    expect(block).toHaveProperty("retry_config");
    expect((block as Record<string, unknown>).retry_config).toEqual({
      max_attempts: 2,
      backoff: "fixed",
      backoff_base_seconds: 5,
    });
  });

  it("retryConfig is emitted as retry_config on a code block", () => {
    const { block } = compileOne(
      mockNode("b1", "code", {
        code: "run()",
        retryConfig: {
          maxAttempts: 5,
          backoff: "exponential",
          backoffBaseSeconds: 1,
        },
      }),
    );
    expect(block).toHaveProperty("retry_config");
  });
});

describe("Generic editor compile contract", () => {
  it("unknown block types compile through the generic path", () => {
    const { block } = compileOne(
      mockNode("b1", "custom_branch", {
        soulRef: "branch_soul",
        customFlag: "enabled",
      }),
    );
    expect(block.type).toBe("custom_branch");
    expect(block).toHaveProperty("custom_flag", "enabled");
  });
});
