/**
 * Red-team tests for RUN-748: YAML editor falsely warns that inline souls are deprecated.
 *
 * Epic 23 (YAML DX Sugar Layer) re-enabled inline `souls:` as optional shorthand.
 * The parser must NOT emit any deprecation warning when it encounters an inline souls section.
 *
 * These tests are expected to FAIL against the current implementation because
 * yamlParser.ts:219 still emits a deprecation error for `souls !== undefined`.
 */

import { describe, it, expect } from "vitest";
import { dump } from "js-yaml";
import { parseWorkflowYamlToGraph } from "../yamlParser";

// ---------------------------------------------------------------------------
// Helper: build minimal valid YAML with an inline souls section
// ---------------------------------------------------------------------------

function makeYamlWithInlineSouls(
  blocks: Record<string, object>,
  souls: object,
): string {
  return dump({
    version: "1.0",
    souls,
    blocks,
    workflow: {
      name: "test",
      entry: Object.keys(blocks)[0] ?? "start",
      transitions: [],
    },
  });
}

function makeYamlWithoutSouls(blocks: Record<string, object>): string {
  return dump({
    version: "1.0",
    blocks,
    workflow: {
      name: "test",
      entry: Object.keys(blocks)[0] ?? "start",
      transitions: [],
    },
  });
}

// ===========================================================================
// AC1 & AC2: No deprecation warning when inline souls are present
// ===========================================================================

describe("RUN-748: Inline souls must not produce a deprecation warning", () => {
  it("result.error is undefined when YAML contains an inline souls section", () => {
    const yaml = makeYamlWithInlineSouls(
      { step1: { type: "linear", soul_ref: "analyst" } },
      {
        analyst: {
          id: "analyst",
          role: "Data Analyst",
          system_prompt: "Analyze data",
          model_name: "gpt-4",
        },
      },
    );

    const result = parseWorkflowYamlToGraph(yaml);

    // The parser must not set an error for a valid inline souls section
    expect(result.error).toBeUndefined();
  });

  it("result.error.message does not contain 'deprecated' when inline souls are present", () => {
    const yaml = makeYamlWithInlineSouls(
      { step1: { type: "linear", soul_ref: "planner" } },
      {
        planner: {
          id: "planner",
          role: "Planner",
          system_prompt: "Plan things",
          model_name: "gpt-4",
        },
      },
    );

    const result = parseWorkflowYamlToGraph(yaml);

    if (result.error) {
      expect(result.error.message).not.toMatch(/deprecated/i);
    } else {
      // No error is the ideal outcome — this assertion always passes
      expect(result.error).toBeUndefined();
    }
  });

  it("result.error.message does not contain 'no longer supported' when inline souls are present", () => {
    const yaml = makeYamlWithInlineSouls(
      { step1: { type: "linear", soul_ref: "writer" } },
      {
        writer: {
          id: "writer",
          role: "Writer",
          system_prompt: "Write copy",
          model_name: "gpt-4",
        },
      },
    );

    const result = parseWorkflowYamlToGraph(yaml);

    if (result.error) {
      expect(result.error.message).not.toMatch(/no longer supported/i);
    } else {
      expect(result.error).toBeUndefined();
    }
  });

  it("nodes are still parsed correctly when YAML contains inline souls", () => {
    const yaml = makeYamlWithInlineSouls(
      {
        step1: { type: "linear", soul_ref: "analyst" },
        step2: { type: "dispatch", soul_refs: ["a", "b"] },
      },
      {
        analyst: { id: "analyst", role: "Analyst", system_prompt: "Analyze", model_name: "gpt-4" },
        a: { id: "a", role: "A", system_prompt: "Do A", model_name: "gpt-4" },
        b: { id: "b", role: "B", system_prompt: "Do B", model_name: "gpt-4" },
      },
    );

    const result = parseWorkflowYamlToGraph(yaml);

    // Nodes parsed correctly
    expect(result.nodes).toHaveLength(2);
    expect(result.nodes[0].data.soulRef).toBe("analyst");
    expect(result.nodes[1].data.soulRefs).toEqual(["a", "b"]);

    // And no deprecation warning
    expect(result.error).toBeUndefined();
  });

  it("YAML without souls section also has no error (baseline — must continue passing)", () => {
    const yaml = makeYamlWithoutSouls({
      step1: { type: "linear" },
    });

    const result = parseWorkflowYamlToGraph(yaml);

    expect(result.error).toBeUndefined();
    expect(result.nodes).toHaveLength(1);
  });
});

// ===========================================================================
// AC3: No mention of inline souls in any warning/error
// ===========================================================================

describe("RUN-748: No warning references souls when parsing valid inline souls YAML", () => {
  it("error message does not mention 'souls' at all when YAML has inline souls section", () => {
    const yaml = makeYamlWithInlineSouls(
      { step1: { type: "linear", soul_ref: "analyst" } },
      {
        analyst: {
          id: "analyst",
          role: "Data Analyst",
          system_prompt: "You analyze data.",
          model_name: "gpt-4",
        },
      },
    );

    const result = parseWorkflowYamlToGraph(yaml);

    // The error field must either be absent or must not reference souls at all
    if (result.error) {
      expect(result.error.message).not.toMatch(/souls/i);
    } else {
      expect(result.error).toBeUndefined();
    }
  });

  it("multiple inline souls do not trigger any souls-related warning", () => {
    const yaml = makeYamlWithInlineSouls(
      {
        step1: { type: "linear", soul_ref: "researcher" },
        step2: { type: "linear", soul_ref: "summarizer" },
        step3: { type: "dispatch", soul_refs: ["researcher", "summarizer"] },
      },
      {
        researcher: {
          id: "researcher",
          role: "Researcher",
          system_prompt: "Research topics",
          model_name: "gpt-4",
        },
        summarizer: {
          id: "summarizer",
          role: "Summarizer",
          system_prompt: "Summarize findings",
          model_name: "gpt-4",
        },
      },
    );

    const result = parseWorkflowYamlToGraph(yaml);

    expect(result.nodes).toHaveLength(3);
    expect(result.error).toBeUndefined();
  });
});
