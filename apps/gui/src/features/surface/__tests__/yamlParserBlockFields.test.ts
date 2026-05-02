import { describe, expect, it } from "vitest";

import { makeYaml, parseFirst } from "./yamlTestBuilders";

describe("YAML parser block field conversion", () => {
  it("maps per-type snake_case fields to StepNodeData camelCase fields", () => {
    expect(parseFirst(makeYaml({ step1: { type: "linear", soul_ref: "analyst" } }))).toEqual(
      expect.objectContaining({ stepType: "linear", soulRef: "analyst" }),
    );
    expect(
      parseFirst(makeYaml({ step1: { type: "dispatch", soul_refs: ["a", "b", "c"] } })),
    ).toEqual(expect.objectContaining({ stepType: "dispatch", soulRefs: ["a", "b", "c"] }));
    expect(
      parseFirst(
        makeYaml({
          step1: {
            type: "synthesize",
            soul_ref: "summarizer",
            input_block_ids: ["step_a", "step_b"],
          },
        }),
      ),
    ).toEqual(
      expect.objectContaining({
        stepType: "synthesize",
        soulRef: "summarizer",
        inputBlockIds: ["step_a", "step_b"],
      }),
    );
    expect(
      parseFirst(
        makeYaml({
          step1: {
            type: "gate",
            soul_ref: "evaluator",
            eval_key: "result.approved",
            extract_field: "details",
          },
        }),
      ),
    ).toEqual(
      expect.objectContaining({
        stepType: "gate",
        soulRef: "evaluator",
        evalKey: "result.approved",
        extractField: "details",
      }),
    );
    expect(
      parseFirst(
        makeYaml({
          step1: {
            type: "file_writer",
            output_path: "/tmp/report.md",
            content_key: "report_content",
          },
        }),
      ),
    ).toEqual(
      expect.objectContaining({
        stepType: "file_writer",
        outputPath: "/tmp/report.md",
        contentKey: "report_content",
      }),
    );
    expect(
      parseFirst(
        makeYaml({
          step1: {
            type: "workflow",
            workflow_ref: "sub_workflow",
            max_depth: 5,
          },
        }),
      ),
    ).toEqual(
      expect.objectContaining({
        stepType: "workflow",
        workflowRef: "sub_workflow",
        maxDepth: 5,
      }),
    );
  });

  it("maps role and code block fields", () => {
    expect(
      parseFirst(
        makeYaml({
          step1: {
            type: "team_lead",
            soul_ref: "lead",
            failure_context_keys: ["error_msg", "stack_trace"],
          },
        }),
      ),
    ).toEqual(
      expect.objectContaining({
        stepType: "team_lead",
        soulRef: "lead",
        failureContextKeys: ["error_msg", "stack_trace"],
      }),
    );
    expect(
      parseFirst(makeYaml({ step1: { type: "engineering_manager", soul_ref: "em" } })),
    ).toEqual(expect.objectContaining({ stepType: "engineering_manager", soulRef: "em" }));
    expect(
      parseFirst(
        makeYaml({
          step1: {
            type: "code",
            code: "print('hello')",
            timeout_seconds: 60,
            allowed_imports: ["json", "math"],
          },
        }),
      ),
    ).toEqual(
      expect.objectContaining({
        stepType: "code",
        code: "print('hello')",
        timeoutSeconds: 60,
        allowedImports: ["json", "math"],
      }),
    );
  });

  it("maps loop fields and omits absent optional loop fields", () => {
    const fullLoop = parseFirst(
      makeYaml({
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
      }),
    );
    const minimalLoop = parseFirst(
      makeYaml({
        step1: {
          type: "loop",
          inner_block_refs: ["single_step"],
        },
      }),
    );

    expect(fullLoop).toEqual(
      expect.objectContaining({
        stepType: "loop",
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
    expect(minimalLoop).toEqual(
      expect.objectContaining({
        stepType: "loop",
        innerBlockRefs: ["single_step"],
      }),
    );
    expect(Object.keys(minimalLoop)).not.toContain("maxRounds");
    expect(Object.keys(minimalLoop)).not.toContain("breakCondition");
    expect(Object.keys(minimalLoop)).not.toContain("carryContext");
  });
});

describe("YAML parser universal field conversion", () => {
  it("maps output_conditions, inputs, and outputs", () => {
    const outputConditions = parseFirst(
      makeYaml({
        step1: {
          type: "linear",
          soul_ref: "analyst",
          output_conditions: [
            {
              case_id: "happy",
              condition_group: {
                combinator: "and",
                conditions: [{ eval_key: "score", operator: "gte", value: 80 }],
              },
            },
            { case_id: "fallback", default: true },
          ],
        },
      }),
    );
    const inputs = parseFirst(
      makeYaml({
        step1: {
          type: "linear",
          soul_ref: "analyst",
          inputs: { context: { from: "upstream.output" } },
        },
      }),
    );
    const outputs = parseFirst(
      makeYaml({
        step1: {
          type: "linear",
          soul_ref: "analyst",
          outputs: { summary: "string", detail: "string" },
        },
      }),
    );

    expect(outputConditions.outputConditions).toHaveLength(2);
    expect(outputConditions.outputConditions![0].case_id).toBe("happy");
    expect(outputConditions.outputConditions![1].default).toBe(true);
    expect(inputs.inputs).toEqual({ context: { from: "upstream.output" } });
    expect(outputs.outputs).toEqual({ summary: "string", detail: "string" });
  });

  it("maps retry_config recursively on representative block types", () => {
    const linear = parseFirst(
      makeYaml({
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
      }),
    );
    const code = parseFirst(
      makeYaml({
        step1: {
          type: "code",
          code: "run()",
          retry_config: {
            max_attempts: 5,
            backoff: "fixed",
            backoff_base_seconds: 1,
          },
        },
      }),
    );
    const loop = parseFirst(
      makeYaml({
        step1: {
          type: "loop",
          inner_block_refs: ["step_a"],
          retry_config: {
            max_attempts: 2,
            backoff: "fixed",
            backoff_base_seconds: 10,
          },
        },
      }),
    );

    expect(linear.retryConfig).toEqual({
      maxAttempts: 3,
      backoff: "exponential",
      backoffBaseSeconds: 2,
      nonRetryableErrors: ["AuthError"],
    });
    expect(code.retryConfig).toEqual({
      maxAttempts: 5,
      backoff: "fixed",
      backoffBaseSeconds: 1,
    });
    expect(loop.retryConfig).toEqual({
      maxAttempts: 2,
      backoff: "fixed",
      backoffBaseSeconds: 10,
    });
  });
});
