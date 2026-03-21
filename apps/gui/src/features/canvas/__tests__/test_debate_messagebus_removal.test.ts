/**
 * RED-TEAM tests for RUN-165: Remove Debate & MessageBus from frontend.
 *
 * Verifies that "debate" and "message_bus" block types, along with their
 * associated fields (soulARef, soulBRef, soul_a_ref, soul_b_ref, iterations),
 * have been fully removed from the frontend codebase.
 *
 * Expected to FAIL against the current implementation (which still has them).
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { compileGraphToWorkflowYaml } from "../yamlCompiler";
import { parseWorkflowYamlToGraph } from "../yamlParser";
import type { StepNodeData, StepType } from "../../../types/schemas/canvas";
import type { Node } from "@xyflow/react";
import { dump } from "js-yaml";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function readSourceFile(relativePath: string): string {
  const canvasDir = resolve(__dirname, "..");
  return readFileSync(resolve(canvasDir, relativePath), "utf-8");
}

function readTypesFile(): string {
  return readFileSync(
    resolve(__dirname, "../../../types/schemas/canvas.ts"),
    "utf-8",
  );
}

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

function makeYaml(blocks: Record<string, object>): string {
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
// 1. StepType union does NOT include "debate" or "message_bus"
// ===========================================================================

describe("StepType union removal", () => {
  it('"debate" is NOT in the StepType union (source check)', () => {
    const source = readTypesFile();
    // Match the StepType definition block and check it doesn't contain "debate"
    const stepTypeMatch = source.match(
      /export type StepType\s*=[\s\S]*?;/,
    );
    expect(stepTypeMatch).toBeTruthy();
    const stepTypeBlock = stepTypeMatch![0];
    expect(stepTypeBlock).not.toContain('"debate"');
  });

  it('"message_bus" is NOT in the StepType union (source check)', () => {
    const source = readTypesFile();
    const stepTypeMatch = source.match(
      /export type StepType\s*=[\s\S]*?;/,
    );
    expect(stepTypeMatch).toBeTruthy();
    const stepTypeBlock = stepTypeMatch![0];
    expect(stepTypeBlock).not.toContain('"message_bus"');
  });

  it("parser does NOT include debate or message_bus as known types", () => {
    const source = readSourceFile("yamlParser.ts");
    // After RUN-223 cleanup, KNOWN_BLOCK_TYPES was removed entirely.
    // Verify debate/message_bus are not referenced as special types.
    expect(source).not.toMatch(/["']debate["']/);
    expect(source).not.toMatch(/["']message_bus["']/);
  });

  it("parser does not treat 'debate' as a known type", () => {
    const yaml = makeYaml({
      step1: { type: "debate", soul_a_ref: "a", soul_b_ref: "b", iterations: 3 },
    });
    const result = parseWorkflowYamlToGraph(yaml);
    // After RUN-221, "debate" is accepted as a generic unknown type (no special handling)
    expect(result.nodes[0].data.stepType).toBe("debate");
  });

  it("parser does not treat 'message_bus' as a known type", () => {
    const yaml = makeYaml({
      step1: { type: "message_bus", soul_refs: ["a", "b"], iterations: 5 },
    });
    const result = parseWorkflowYamlToGraph(yaml);
    // After RUN-221, "message_bus" is accepted as a generic unknown type (no special handling)
    expect(result.nodes[0].data.stepType).toBe("message_bus");
  });
});

// ===========================================================================
// 2. StepNodeData does NOT have soulARef, soulBRef, or iterations
// ===========================================================================

describe("StepNodeData field removal", () => {
  it("StepNodeData interface does NOT contain soulARef", () => {
    const source = readTypesFile();
    const interfaceMatch = source.match(
      /export interface StepNodeData[\s\S]*?^}/m,
    );
    expect(interfaceMatch).toBeTruthy();
    const interfaceBlock = interfaceMatch![0];
    expect(interfaceBlock).not.toContain("soulARef");
  });

  it("StepNodeData interface does NOT contain soulBRef", () => {
    const source = readTypesFile();
    const interfaceMatch = source.match(
      /export interface StepNodeData[\s\S]*?^}/m,
    );
    expect(interfaceMatch).toBeTruthy();
    const interfaceBlock = interfaceMatch![0];
    expect(interfaceBlock).not.toContain("soulBRef");
  });

  it("StepNodeData interface does NOT contain iterations", () => {
    const source = readTypesFile();
    const interfaceMatch = source.match(
      /export interface StepNodeData[\s\S]*?^}/m,
    );
    expect(interfaceMatch).toBeTruthy();
    const interfaceBlock = interfaceMatch![0];
    expect(interfaceBlock).not.toContain("iterations");
  });

  it("StepNodeData interface still contains soulRefs (used by FanOut)", () => {
    const source = readTypesFile();
    const interfaceMatch = source.match(
      /export interface StepNodeData[\s\S]*?^}/m,
    );
    expect(interfaceMatch).toBeTruthy();
    const interfaceBlock = interfaceMatch![0];
    expect(interfaceBlock).toContain("soulRefs");
  });
});

// ===========================================================================
// 3. BlockDef does NOT have soul_a_ref, soul_b_ref, or iterations
// ===========================================================================

describe("BlockDef field removal", () => {
  it("BlockDef interface does NOT contain soul_a_ref", () => {
    const source = readTypesFile();
    const interfaceMatch = source.match(
      /export interface BlockDef[\s\S]*?^}/m,
    );
    expect(interfaceMatch).toBeTruthy();
    const interfaceBlock = interfaceMatch![0];
    expect(interfaceBlock).not.toContain("soul_a_ref");
  });

  it("BlockDef interface does NOT contain soul_b_ref", () => {
    const source = readTypesFile();
    const interfaceMatch = source.match(
      /export interface BlockDef[\s\S]*?^}/m,
    );
    expect(interfaceMatch).toBeTruthy();
    const interfaceBlock = interfaceMatch![0];
    expect(interfaceBlock).not.toContain("soul_b_ref");
  });

  it("BlockDef interface does NOT contain iterations", () => {
    const source = readTypesFile();
    const interfaceMatch = source.match(
      /export interface BlockDef[\s\S]*?^}/m,
    );
    expect(interfaceMatch).toBeTruthy();
    const interfaceBlock = interfaceMatch![0];
    expect(interfaceBlock).not.toContain("iterations");
  });

  it("BlockDef interface still contains soul_refs (used by FanOut)", () => {
    const source = readTypesFile();
    const interfaceMatch = source.match(
      /export interface BlockDef[\s\S]*?^}/m,
    );
    expect(interfaceMatch).toBeTruthy();
    const interfaceBlock = interfaceMatch![0];
    expect(interfaceBlock).toContain("soul_refs");
  });
});

// ===========================================================================
// 4. BLOCK_TYPE_FIELDS does NOT have "debate" or "message_bus" entries
// ===========================================================================

describe("BLOCK_TYPE_FIELDS removal", () => {
  it('compiler does NOT have a BLOCK_TYPE_FIELDS constant (removed in RUN-223)', () => {
    const source = readSourceFile("yamlCompiler.ts");
    // After RUN-223, BLOCK_TYPE_FIELDS was removed entirely.
    expect(source).not.toMatch(/\bBLOCK_TYPE_FIELDS\b/);
  });

  it('compiler does NOT have a "message_bus" entry', () => {
    const source = readSourceFile("yamlCompiler.ts");
    // No reference to message_bus as a block type
    expect(source).not.toMatch(/\bmessage_bus\b/);
  });

  it("compiler does NOT produce soul_a_ref or soul_b_ref fields", () => {
    // Even if we force-cast "debate" as a StepType, the compiler should
    // NOT have field mappings for soul_a_ref / soul_b_ref
    const source = readSourceFile("yamlCompiler.ts");
    expect(source).not.toContain("soul_a_ref");
    expect(source).not.toContain("soul_b_ref");
  });
});

// ===========================================================================
// 5. CAMEL_TO_SNAKE does NOT have soulARef or soulBRef mappings
// ===========================================================================

describe("CAMEL_TO_SNAKE mapping removal", () => {
  it("compiler does NOT have a CAMEL_TO_SNAKE constant (removed in RUN-223)", () => {
    const source = readSourceFile("yamlCompiler.ts");
    // After RUN-223, CAMEL_TO_SNAKE was removed entirely.
    expect(source).not.toMatch(/\bCAMEL_TO_SNAKE\b/);
  });

  it("compiler does NOT reference soulARef or soulBRef", () => {
    const source = readSourceFile("yamlCompiler.ts");
    expect(source).not.toContain("soulARef");
    expect(source).not.toContain("soulBRef");
  });

  it("compiler does NOT reference iterations as a hardcoded field", () => {
    const source = readSourceFile("yamlCompiler.ts");
    expect(source).not.toContain("iterations");
  });
});

// ===========================================================================
// 6. YAML parser snake-to-camel does NOT have soul_a_ref or soul_b_ref
// ===========================================================================

describe("Parser snake-to-camel mapping removal", () => {
  it("parser buildNodeData does NOT map soul_a_ref -> soulARef", () => {
    const source = readSourceFile("yamlParser.ts");
    expect(source).not.toContain("soul_a_ref");
    expect(source).not.toContain("soulARef");
  });

  it("parser buildNodeData does NOT map soul_b_ref -> soulBRef", () => {
    const source = readSourceFile("yamlParser.ts");
    expect(source).not.toContain("soul_b_ref");
    expect(source).not.toContain("soulBRef");
  });

  it("parser buildNodeData does NOT map iterations", () => {
    const source = readSourceFile("yamlParser.ts");
    // Should not have any line setting data.iterations from block.iterations
    expect(source).not.toMatch(/block\.iterations/);
    expect(source).not.toMatch(/data\.iterations/);
  });
});

// ===========================================================================
// 7. soulRefs MUST still be present (FanOut needs it)
// ===========================================================================

describe("soulRefs preservation for FanOut", () => {
  it("FanOut block still compiles soulRefs -> soul_refs", () => {
    const node = mockNode("fan", "fanout", { soulRefs: ["s1", "s2"] });
    const result = compileGraphToWorkflowYaml({ nodes: [node], edges: [] });
    const block = result.workflowDocument.blocks["fan"];

    expect(block.type).toBe("fanout");
    expect(block).toHaveProperty("soul_refs", ["s1", "s2"]);
  });

  it("FanOut block still parses soul_refs -> soulRefs", () => {
    const yaml = makeYaml({
      fan: { type: "fanout", soul_refs: ["a", "b", "c"] },
    });
    const result = parseWorkflowYamlToGraph(yaml);
    const data = result.nodes[0].data;

    expect(data.stepType).toBe("fanout");
    expect(data.soulRefs).toEqual(["a", "b", "c"]);
  });

  it("compiler still converts soulRefs to soul_refs via camelToSnake", () => {
    const source = readSourceFile("yamlCompiler.ts");
    // After RUN-223, camelToSnake function handles conversion generically
    expect(source).toContain("camelToSnake");
  });
});

// ===========================================================================
// 8. No debate/message_bus references remain in source files
// ===========================================================================

describe("No debate/message_bus references in source files", () => {
  const sourceFiles = [
    { path: "yamlCompiler.ts", label: "yamlCompiler" },
    { path: "yamlParser.ts", label: "yamlParser" },
  ];

  for (const { path, label } of sourceFiles) {
    it(`${label} does NOT contain "debate"`, () => {
      const source = readSourceFile(path);
      expect(source).not.toMatch(/\bdebate\b/);
    });

    it(`${label} does NOT contain "message_bus"`, () => {
      const source = readSourceFile(path);
      expect(source).not.toMatch(/\bmessage_bus\b/);
    });

    it(`${label} does NOT contain "soulARef"`, () => {
      const source = readSourceFile(path);
      expect(source).not.toContain("soulARef");
    });

    it(`${label} does NOT contain "soulBRef"`, () => {
      const source = readSourceFile(path);
      expect(source).not.toContain("soulBRef");
    });

    it(`${label} does NOT contain "soul_a_ref"`, () => {
      const source = readSourceFile(path);
      expect(source).not.toContain("soul_a_ref");
    });

    it(`${label} does NOT contain "soul_b_ref"`, () => {
      const source = readSourceFile(path);
      expect(source).not.toContain("soul_b_ref");
    });
  }

  it('types/schemas/canvas.ts does NOT contain "debate" in StepType', () => {
    const source = readTypesFile();
    const stepTypeMatch = source.match(
      /export type StepType\s*=[\s\S]*?;/,
    );
    expect(stepTypeMatch).toBeTruthy();
    expect(stepTypeMatch![0]).not.toContain('"debate"');
  });

  it('types/schemas/canvas.ts does NOT contain "message_bus" in StepType', () => {
    const source = readTypesFile();
    const stepTypeMatch = source.match(
      /export type StepType\s*=[\s\S]*?;/,
    );
    expect(stepTypeMatch).toBeTruthy();
    expect(stepTypeMatch![0]).not.toContain('"message_bus"');
  });
});

// ===========================================================================
// 9. Behavioral: compiler/parser no longer process debate/message_bus fields
// ===========================================================================

describe("Behavioral validation", () => {
  it("compiling a node with extra fields emits them via generic path", () => {
    // After RUN-223, the generic path emits ALL non-runtime fields for all types.
    const node: Node<StepNodeData> = {
      id: "b1",
      type: "canvasNode",
      position: { x: 0, y: 0 },
      data: {
        stepId: "b1",
        name: "b1",
        stepType: "linear" as StepType,
        status: "idle",
        ...(({ soulARef: "alice", soulBRef: "bob", iterations: 5 }) as unknown as Partial<StepNodeData>),
      },
    };

    const result = compileGraphToWorkflowYaml({ nodes: [node], edges: [] });
    const block = result.workflowDocument.blocks["b1"] as Record<string, unknown>;

    // Generic path emits all fields with camelToSnake conversion
    expect(block).toHaveProperty("soul_a_ref", "alice");
    expect(block).toHaveProperty("soul_b_ref", "bob");
    expect(block).toHaveProperty("iterations", 5);
  });

  it("parsing YAML with extra fields maps them to node data via generic path", () => {
    // After RUN-223, the generic path maps all block fields for all types.
    const yaml = makeYaml({
      step1: {
        type: "linear",
        soul_ref: "agent",
        soul_a_ref: "alice",
        soul_b_ref: "bob",
        iterations: 5,
      },
    });
    const result = parseWorkflowYamlToGraph(yaml);
    const data = result.nodes[0].data;

    // Generic path converts snake_case to camelCase for top-level keys
    expect(data.soulRef).toBe("agent");
    expect(data.soulARef).toBe("alice");
    expect(data.soulBRef).toBe("bob");
    expect(data.iterations).toBe(5);
  });
});
