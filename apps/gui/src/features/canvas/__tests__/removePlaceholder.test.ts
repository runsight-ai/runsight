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

  it("parser VALID_STEP_TYPES does NOT include placeholder", () => {
    const source = readSourceFile("yamlParser.ts");
    const validSetMatch = source.match(
      /VALID_STEP_TYPES\s*=\s*new Set[^)]*\(\[[\s\S]*?\]\)/,
    );
    expect(validSetMatch).toBeTruthy();
    const setBlock = validSetMatch![0];
    expect(setBlock).not.toContain('"placeholder"');
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
  it('BLOCK_TYPE_FIELDS does NOT have a "placeholder" entry', () => {
    const source = readSourceFile("yamlCompiler.ts");
    const fieldsMatch = source.match(
      /BLOCK_TYPE_FIELDS[\s\S]*?^};/m,
    );
    expect(fieldsMatch).toBeTruthy();
    const fieldsBlock = fieldsMatch![0];
    expect(fieldsBlock).not.toMatch(/\bplaceholder\b/);
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
    // After removal, invalid types should NOT fall back to "placeholder"
    // They should produce an error or return something like "unknown"
    if (result.nodes.length > 0) {
      expect(result.nodes[0].data.stepType).not.toBe("placeholder");
    }
    // Either an error is surfaced or stepType is not "placeholder"
    const hasError = result.error !== undefined;
    const notPlaceholder =
      result.nodes.length > 0 && result.nodes[0].data.stepType !== "placeholder";
    expect(hasError || notPlaceholder).toBe(true);
  });

  it("parser does NOT return 'placeholder' for missing type field", () => {
    const yaml = makeYaml({
      step1: { soul_ref: "agent" }, // no type field at all
    });
    const result = parseWorkflowYamlToGraph(yaml);
    if (result.nodes.length > 0) {
      expect(result.nodes[0].data.stepType).not.toBe("placeholder");
    }
    const hasError = result.error !== undefined;
    const notPlaceholder =
      result.nodes.length > 0 && result.nodes[0].data.stepType !== "placeholder";
    expect(hasError || notPlaceholder).toBe(true);
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

  it("parser does NOT return 'placeholder' when YAML has type: placeholder", () => {
    const yaml = makeYaml({
      step1: { type: "placeholder", description: "TODO" },
    });
    const result = parseWorkflowYamlToGraph(yaml);
    // "placeholder" is no longer a valid type — should be treated as invalid
    if (result.nodes.length > 0) {
      expect(result.nodes[0].data.stepType).not.toBe("placeholder");
    }
    const hasError = result.error !== undefined;
    const notPlaceholder =
      result.nodes.length > 0 && result.nodes[0].data.stepType !== "placeholder";
    expect(hasError || notPlaceholder).toBe(true);
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

  it("compiler CAMEL_TO_SNAKE does NOT map description", () => {
    const source = readSourceFile("yamlCompiler.ts");
    const mappingMatch = source.match(
      /CAMEL_TO_SNAKE[\s\S]*?^};/m,
    );
    expect(mappingMatch).toBeTruthy();
    const mappingBlock = mappingMatch![0];
    // description was only used by placeholder blocks
    expect(mappingBlock).not.toContain("description");
  });
});

// ===========================================================================
// 7. WorkflowCanvas displays "unknown" (not "placeholder") for missing type
// ===========================================================================

describe("Canvas display fallback", () => {
  it('WorkflowCanvas.tsx uses "unknown" instead of "placeholder" as display fallback', () => {
    const source = readSourceFile("WorkflowCanvas.tsx");
    // The old fallback was: {typedData.stepType ?? "placeholder"}
    // It should now be: {typedData.stepType ?? "unknown"} (or similar)
    expect(source).not.toContain('"placeholder"');
    // Verify "unknown" is used as the display fallback
    expect(source).toContain('"unknown"');
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
  it("YAML with type: placeholder is treated as invalid — does not parse as placeholder", () => {
    const yaml = makeYaml({
      step1: { type: "placeholder", description: "legacy node" },
    });
    const result = parseWorkflowYamlToGraph(yaml);
    // Should either error or parse as unknown/error type — never "placeholder"
    if (result.nodes.length > 0) {
      expect(result.nodes[0].data.stepType).not.toBe("placeholder");
    }
  });

  it("compiler does NOT produce description field for any block type", () => {
    // Even if we force description into node data, the compiler should not emit it
    // since it was placeholder-only and placeholder is removed
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
        ...(({ description: "should not appear" }) as unknown as Partial<StepNodeData>),
      },
    };

    const result = compileGraphToWorkflowYaml({ nodes: [node], edges: [] });
    const block = result.workflowDocument.blocks["b1"];

    expect(block).not.toHaveProperty("description");
    expect(result.yaml).not.toMatch(/^\s+description:/m);
  });

  it("parser buildNodeData does NOT set description from block data", () => {
    // Even if YAML has a description field on a non-placeholder block,
    // after removal it should not be mapped to node data
    const yaml = makeYaml({
      step1: { type: "linear", soul_ref: "agent", description: "should be ignored" },
    });
    const result = parseWorkflowYamlToGraph(yaml);
    const data = result.nodes[0].data;
    const keys = Object.keys(data);
    expect(keys).not.toContain("description");
  });
});
