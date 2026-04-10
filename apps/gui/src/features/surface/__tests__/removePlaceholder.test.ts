/**
 * RED-TEAM tests for RUN-205: Remove PlaceholderBlock from frontend.
 *
 * Verifies that "placeholder" block type, its associated fields (description),
 * the DEFAULT_STEP_TYPE constant, and all placeholder fallbacks have been
 * fully removed from the frontend codebase.
 *
 * Expected to FAIL against the current implementation (which still has them).
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { compileGraphToWorkflowYaml } from "../yamlCompiler";
import { parseWorkflowYamlToGraph } from "../yamlParser";
import type { StepNodeData, StepType } from "../../../types/schemas/canvas";
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
// 1. StepType union does NOT include "placeholder"
// ===========================================================================

describe("StepType union removal", () => {
  it('"placeholder" is NOT in the StepType union (source check)', () => {
    const source = readTypesFile();
    const stepTypeMatch = source.match(
      /export type StepType\s*=[\s\S]*?;/,
    );
    expect(stepTypeMatch).toBeTruthy();
    const stepTypeBlock = stepTypeMatch![0];
    expect(stepTypeBlock).not.toContain('"placeholder"');
  });

  it("parser does NOT include placeholder as a known type", () => {
    const source = readSourceFile("yamlParser.ts");
    // After RUN-223 cleanup, KNOWN_BLOCK_TYPES was removed entirely.
    // Verify placeholder is not referenced as a special type.
    expect(source).not.toMatch(/["']placeholder["']/);
  });
});

// ===========================================================================
// 2. StepNodeData does NOT have description field
// ===========================================================================

describe("StepNodeData description field removal", () => {
  it("StepNodeData interface does NOT contain description field", () => {
    const source = readTypesFile();
    const interfaceMatch = source.match(
      /export interface StepNodeData[\s\S]*?^}/m,
    );
    expect(interfaceMatch).toBeTruthy();
    const interfaceBlock = interfaceMatch![0];
    // Should not have a description field (PlaceholderBlock-specific)
    expect(interfaceBlock).not.toMatch(/\bdescription\b/);
  });
});

// ===========================================================================
// 3. DEFAULT_STEP_TYPE constant does NOT exist
// ===========================================================================

describe("DEFAULT_STEP_TYPE removal", () => {
  it("yamlParser.ts does NOT export or define DEFAULT_STEP_TYPE", () => {
    const source = readSourceFile("yamlParser.ts");
    expect(source).not.toContain("DEFAULT_STEP_TYPE");
  });
});

// ===========================================================================
// 4. BLOCK_TYPE_FIELDS does NOT have a "placeholder" entry
// ===========================================================================

describe("BLOCK_TYPE_FIELDS removal", () => {
  it('compiler does NOT have a BLOCK_TYPE_FIELDS constant (removed in RUN-223)', () => {
    const source = readSourceFile("yamlCompiler.ts");
    // After RUN-223, BLOCK_TYPE_FIELDS was removed entirely.
    expect(source).not.toMatch(/\bBLOCK_TYPE_FIELDS\b/);
  });
});

// ===========================================================================
// 5. toStepType() does NOT return "placeholder" for invalid input
// ===========================================================================

describe("toStepType() no placeholder fallback", () => {
  it("parser does NOT return 'placeholder' for invalid type strings", () => {
    const yaml = makeYaml({
      step1: { type: "totally_invalid_type", soul_ref: "agent" },
    });
    const result = parseWorkflowYamlToGraph(yaml);
    // After RUN-221, unknown types are accepted generically (no error, no fallback)
    if (result.nodes.length > 0) {
      expect(result.nodes[0].data.stepType).not.toBe("placeholder");
    }
  });

  it("parser does NOT return 'placeholder' for missing type field", () => {
    const yaml = makeYaml({
      step1: { soul_ref: "agent" }, // no type field at all
    });
    const result = parseWorkflowYamlToGraph(yaml);
    // Missing type must produce validation feedback, not a silent fallback
    if (result.nodes.length > 0) {
      expect(result.nodes[0].data.stepType).not.toBe("placeholder");
    }
    expect(result.error).toBeDefined();
    expect(result.error!.message).toBeTruthy();
  });

  it("parser does NOT return 'placeholder' for non-string type", () => {
    const yaml = makeYaml({
      step1: { type: 42 },
    });
    const result = parseWorkflowYamlToGraph(yaml);
    if (result.nodes.length > 0) {
      expect(result.nodes[0].data.stepType).not.toBe("placeholder");
    }
  });

  it("parser does NOT treat 'placeholder' as a known type with special handling", () => {
    const yaml = makeYaml({
      step1: { type: "placeholder", description: "TODO" },
    });
    const result = parseWorkflowYamlToGraph(yaml);
    // After RUN-221, "placeholder" is accepted as a generic unknown type
    // (no special placeholder handling, no fallback, no error)
    expect(result.nodes).toHaveLength(1);
    // It is NOT in the known types, so it gets generic handling
    expect(result.nodes[0].data.stepType).toBe("placeholder");
  });
});

// ===========================================================================
// 6. Compiler does NOT use "placeholder" as a fallback
// ===========================================================================

describe("Compiler no placeholder fallback", () => {
  it('compiler toCompiledBlock does NOT fall back to "placeholder"', () => {
    const source = readSourceFile("yamlCompiler.ts");
    // Should NOT have ?? "placeholder" anywhere
    expect(source).not.toContain('"placeholder"');
  });

  it("compiler does NOT have a CAMEL_TO_SNAKE constant (removed in RUN-223)", () => {
    const source = readSourceFile("yamlCompiler.ts");
    // After RUN-223, CAMEL_TO_SNAKE was removed entirely.
    expect(source).not.toMatch(/\bCAMEL_TO_SNAKE\b/);
  });
});

// ===========================================================================
// 7. WorkflowCanvas no longer contains placeholder-specific fallback logic
// ===========================================================================

describe("Canvas display fallback", () => {
  it("WorkflowCanvas.tsx does not encode placeholder-specific display fallback", () => {
    const source = readSourceFile("WorkflowCanvas.tsx");
    expect(source).not.toContain('"placeholder"');
  });
});

// ===========================================================================
// 8. No placeholder references remain in source files
// ===========================================================================

describe("No placeholder references in source files", () => {
  const sourceFiles = [
    { path: "yamlCompiler.ts", label: "yamlCompiler" },
    { path: "yamlParser.ts", label: "yamlParser" },
  ];

  for (const { path, label } of sourceFiles) {
    it(`${label} does NOT contain "placeholder" as a block type reference`, () => {
      const source = readSourceFile(path);
      expect(source).not.toMatch(/["']placeholder["']/);
    });
  }

  it('types/schemas/canvas.ts does NOT contain "placeholder" in StepType', () => {
    const source = readTypesFile();
    const stepTypeMatch = source.match(
      /export type StepType\s*=[\s\S]*?;/,
    );
    expect(stepTypeMatch).toBeTruthy();
    expect(stepTypeMatch![0]).not.toContain('"placeholder"');
  });
});

// ===========================================================================
// 9. BlockDef does NOT have description field
// ===========================================================================

describe("BlockDef description field removal", () => {
  it("BlockDef interface does NOT contain description field", () => {
    const source = readTypesFile();
    const interfaceMatch = source.match(
      /export interface BlockDef[\s\S]*?^}/m,
    );
    expect(interfaceMatch).toBeTruthy();
    const interfaceBlock = interfaceMatch![0];
    expect(interfaceBlock).not.toMatch(/\bdescription\b/);
  });
});

// ===========================================================================
// 10. Behavioral: existing workflows with placeholder type show as unknown
// ===========================================================================

describe("Behavioral validation", () => {
  it("YAML with type: placeholder is treated as a generic unknown type", () => {
    const yaml = makeYaml({
      step1: { type: "placeholder", description: "legacy node" },
    });
    const result = parseWorkflowYamlToGraph(yaml);
    // After RUN-221, "placeholder" is accepted as a generic unknown type
    expect(result.nodes).toHaveLength(1);
    expect(result.nodes[0].data.stepType).toBe("placeholder");
  });

  it("compiler emits all data fields via generic path (including extra fields)", () => {
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
        soulRef: "agent",
        ...(({ description: "some description" }) as unknown as Partial<StepNodeData>),
      },
    };

    const result = compileGraphToWorkflowYaml({ nodes: [node], edges: [] });
    const block = result.workflowDocument.blocks["b1"] as Record<string, unknown>;

    // Generic path emits all fields — description is included
    expect(block).toHaveProperty("soul_ref", "agent");
    expect(block).toHaveProperty("description", "some description");
  });

  it("parser maps all block fields to node data via generic path", () => {
    // After RUN-223, the generic path maps all block fields for all types.
    const yaml = makeYaml({
      step1: { type: "linear", soul_ref: "agent", description: "extra field" },
    });
    const result = parseWorkflowYamlToGraph(yaml);
    const data = result.nodes[0].data;
    expect(data.soulRef).toBe("agent");
    // Generic path maps description to node data
    expect(data.description).toBe("extra field");
  });
});
