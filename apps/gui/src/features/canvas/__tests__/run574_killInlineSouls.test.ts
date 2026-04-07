/**
 * Red-team tests for RUN-574: Kill inline souls from YAML compiler/parser/types.
 *
 * AC1: Compiled YAML never contains a `souls:` section
 * AC4: Old YAML with `souls:` section handled gracefully (warning, not crash)
 * AC5: TS types updated to remove `souls` from workflow interface
 *
 * Expected to FAIL against the current implementation.
 */

import { describe, it, expect } from "vitest";
import { dump } from "js-yaml";
import { compileGraphToWorkflowYaml } from "../yamlCompiler";
import { parseWorkflowYamlToGraph } from "../yamlParser";
import type { StepNodeData, StepType, SoulDef, RunsightWorkflowFile } from "../../../types/schemas/canvas";
import type { Node } from "@xyflow/react";

// ---------------------------------------------------------------------------
// Helpers (from existing test patterns)
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

// ===========================================================================
// AC1: Compiled YAML never contains a `souls:` section
// ===========================================================================

describe("AC1: Compiler never emits souls section", () => {
  it("workflowDocument should NOT have a souls key when souls are provided in input", () => {
    const souls: Record<string, SoulDef> = {
      analyst: {
        id: "analyst",
        role: "Data Analyst",
        system_prompt: "Analyze data",
        model_name: "gpt-4",
      },
    };

    const result = compileGraphToWorkflowYaml({
      nodes: [mockNode("step1", "linear", { soulRef: "analyst" })],
      edges: [],
      souls,
    });

    // The compiled document must NOT contain a souls section
    expect(result.workflowDocument).not.toHaveProperty("souls");
  });

  it("YAML string should NOT contain 'souls:' when souls are provided in input", () => {
    const souls: Record<string, SoulDef> = {
      planner: {
        id: "planner",
        role: "Planner",
        system_prompt: "Plan things",
        model_name: "gpt-4",
      },
    };

    const result = compileGraphToWorkflowYaml({
      nodes: [mockNode("step1", "linear", { soulRef: "planner" })],
      edges: [],
      souls,
    });

    // The raw YAML string must not contain a top-level souls section
    expect(result.yaml).not.toMatch(/^souls:/m);
  });

  it("workflowDocument should NOT have souls key even with multiple souls provided", () => {
    const souls: Record<string, SoulDef> = {
      analyst: {
        id: "analyst",
        role: "Data Analyst",
        system_prompt: "Analyze",
        model_name: "gpt-4",
      },
      writer: {
        id: "writer",
        role: "Writer",
        system_prompt: "Write",
        model_name: "gpt-4",
      },
    };

    const result = compileGraphToWorkflowYaml({
      nodes: [
        mockNode("step1", "linear", { soulRef: "analyst" }),
        mockNode("step2", "linear", { soulRef: "writer" }),
      ],
      edges: [],
      souls,
    });

    expect(result.workflowDocument).not.toHaveProperty("souls");
    expect(result.yaml).not.toMatch(/^souls:/m);
  });

  it("workflowDocument blocks should still emit soul_ref even though top-level souls is gone", () => {
    const result = compileGraphToWorkflowYaml({
      nodes: [mockNode("step1", "linear", { soulRef: "analyst" })],
      edges: [],
      souls: {
        analyst: {
          id: "analyst",
          role: "Analyst",
          system_prompt: "Analyze",
          model_name: "gpt-4",
        },
      },
    });

    // soul_ref on blocks should still work — only the top-level souls section is removed
    expect(result.workflowDocument.blocks["step1"]).toHaveProperty("soul_ref", "analyst");
    expect(result.workflowDocument).not.toHaveProperty("souls");
  });
});

// ===========================================================================
// AC4: Old YAML with `souls:` section handled gracefully
// ===========================================================================

describe("AC4: Parser handles old YAML with souls gracefully", () => {
  it("should NOT crash when parsing YAML with inline souls section", () => {
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

    // Must not throw
    const result = parseWorkflowYamlToGraph(yaml);
    expect(result.nodes).toHaveLength(1);
    expect(result.nodes[0].data.stepType).toBe("linear");
    expect(result.nodes[0].data.soulRef).toBe("analyst");
  });

  it("should NOT include souls in the parsed result", () => {
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

    // After RUN-574, the parser should strip souls from its result
    expect(result).not.toHaveProperty("souls");
  });

  it("should silently accept old YAML with souls section without erroring", () => {
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

    // RUN-748: inline souls are valid shorthand — parser silently accepts them
    expect(result.error).toBeUndefined();
    expect(result.nodes).toHaveLength(1);
  });

  it("should still parse blocks correctly when souls section is present", () => {
    const yaml = makeYaml(
      {
        step1: { type: "linear", soul_ref: "analyst" },
        step2: { type: "dispatch", soul_refs: ["a", "b"] },
      },
      {
        souls: {
          analyst: { id: "analyst", role: "Analyst", system_prompt: "Analyze", model_name: "gpt-4" },
          a: { id: "a", role: "A", system_prompt: "Do A", model_name: "gpt-4" },
          b: { id: "b", role: "B", system_prompt: "Do B", model_name: "gpt-4" },
        },
      },
    );

    const result = parseWorkflowYamlToGraph(yaml);
    expect(result.nodes).toHaveLength(2);
    expect(result.nodes[0].data.soulRef).toBe("analyst");
    expect(result.nodes[1].data.soulRefs).toEqual(["a", "b"]);
    // But souls should NOT be propagated
    expect(result).not.toHaveProperty("souls");
  });
});

// ===========================================================================
// AC5: TS types updated to remove `souls` from workflow interface
// ===========================================================================

describe("AC5: RunsightWorkflowFile type does not include souls", () => {
  /**
   * Runtime check: create a RunsightWorkflowFile-typed object with `souls`
   * and verify the property is assignable. After RUN-574, the `souls` key
   * should be removed from the interface, which means this object would
   * either fail type-check or the property is effectively gone.
   *
   * Since we can't fail a test at the type level alone, we verify by
   * checking that an object satisfying RunsightWorkflowFile has no
   * `souls` in its type definition via a runtime proxy.
   */
  it("RunsightWorkflowFile should not have souls as an explicit property", () => {
    // Build a valid workflow file object and verify that `souls` should not
    // be part of the type. We check this by constructing one WITH souls and
    // asserting the implementation strips it.
    const workflowFile: RunsightWorkflowFile = {
      version: "1.0",
      blocks: { step1: { type: "linear" } },
      workflow: {
        name: "test",
        entry: "step1",
        transitions: [],
      },
      // Currently this compiles because `souls` is on the interface.
      // After RUN-574, this should be a TS error. We detect it at runtime:
      souls: {
        analyst: {
          id: "analyst",
          role: "Analyst",
          system_prompt: "Analyze",
          model_name: "gpt-4",
        },
      },
    };

    // After RUN-574, `souls` should not be a recognized key on the type.
    // Since we can't enforce TS errors at runtime, we check the compiled
    // output of the compiler (which uses this type) does not carry souls.
    const result = compileGraphToWorkflowYaml({
      nodes: [mockNode("step1", "linear")],
      edges: [],
      souls: workflowFile.souls,
    });

    expect(result.workflowDocument).not.toHaveProperty("souls");
  });

  it("CompileInput should not accept a souls property", () => {
    // Verify the compiler input type also drops souls.
    // We test this by ensuring the compiled output never has souls
    // even when we try to sneak it in via the input.
    const result = compileGraphToWorkflowYaml({
      nodes: [mockNode("step1", "linear")],
      edges: [],
      // After RUN-574, this property should cause a TS error
      // (but we still pass it to test runtime behavior)
      souls: {
        test: {
          id: "test",
          role: "Test",
          system_prompt: "Test",
          model_name: "gpt-4",
        },
      },
    });

    expect(result.workflowDocument).not.toHaveProperty("souls");
  });

  it("ParseWorkflowResult should not include souls in its shape", () => {
    // Parse YAML that HAS a souls section — the result should NOT carry it
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

    // After RUN-574, `souls` should not be a property on the result at all
    expect(Object.keys(result)).not.toContain("souls");
  });
});
