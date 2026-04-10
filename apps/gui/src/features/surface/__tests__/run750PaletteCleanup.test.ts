/**
 * RED-TEAM tests for RUN-750: Canvas palette lists removed FileWriter block
 * and compiler silently defaults missing stepType to linear.
 *
 * Problem 1 (PaletteSidebar.tsx:13):
 *   `FileWriter` remains in the BLOCK_TYPES array. The engine removed this
 *   block type, so dragging it onto the canvas creates an invalid node.
 *
 * Problem 2 (yamlCompiler.ts:64):
 *   `data?.stepType ?? ("linear" as StepType)` silently produces a `linear`
 *   LLM block in YAML for any node with an unrecognised or missing stepType.
 *
 * Expected failures (current state — tests are RED):
 *   - FileWriter IS currently in BLOCK_TYPES  → tests asserting its absence fail
 *   - Compiler DOES silently default to linear → tests asserting rejection fail
 *   - Drop handler does NOT validate blockType → test asserting guard fails (source-level)
 *
 * Acceptance criteria from RUN-750:
 *   AC1  Remove `FileWriter` from `BLOCK_TYPES` in PaletteSidebar.tsx
 *   AC2  Palette only lists block types that exist in the core engine
 *   AC3  Drop handler validates `stepType` against a canonical list before creating the node
 *   AC4  Compiler rejects or warns on unknown stepType instead of silently defaulting to linear
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { Node } from "@xyflow/react";
import type { StepNodeData, StepType } from "../../../types/schemas/canvas";
import { compileGraphToWorkflowYaml } from "../yamlCompiler";

// ---------------------------------------------------------------------------
// Path helpers (source-reading tests)
// ---------------------------------------------------------------------------

const SRC_DIR = resolve(__dirname, "../../..");

function readSource(relativePath: string): string {
  return readFileSync(resolve(SRC_DIR, relativePath), "utf-8");
}

// ---------------------------------------------------------------------------
// Canonical engine block types (from StepType union in canvas.ts, minus the
// open `string & {}` escape hatch).  FileWriter / file-writer are NOT here.
// ---------------------------------------------------------------------------

const CANONICAL_ENGINE_TYPES = new Set<string>([
  "linear",
  "dispatch",
  "gate",
  "synthesize",
  "workflow",
  "loop",
  "team_lead",
  "engineering_manager",
  "file_writer",   // snake_case engine name — distinct from the "FileWriter" UI label
  "code",
  "http_request",
]);

// ---------------------------------------------------------------------------
// Helper: compile a single node
// ---------------------------------------------------------------------------

function mockNode(
  id: string,
  stepType: StepType | undefined,
  extraData: Partial<StepNodeData> = {},
): Node<StepNodeData> {
  return {
    id,
    type: "canvasNode",
    position: { x: 0, y: 0 },
    data: {
      stepId: id,
      name: id,
      stepType: stepType as StepType,
      status: "idle",
      ...extraData,
    },
  };
}

function compileOne(node: Node<StepNodeData>) {
  const result = compileGraphToWorkflowYaml({ nodes: [node], edges: [] });
  return {
    block: result.workflowDocument.blocks[node.id],
    yaml: result.yaml,
  };
}

// ===========================================================================
// 1. PaletteSidebar — FileWriter must be absent (AC1)
// ===========================================================================

describe("PaletteSidebar — FileWriter removed (AC1)", () => {
  const PALETTE_PATH = "features/surface/PaletteSidebar.tsx";

  it("BLOCK_TYPES does NOT contain a 'FileWriter' entry", () => {
    const source = readSource(PALETTE_PATH);

    // Extract the BLOCK_TYPES array literal so we only inspect the array,
    // not any import or comment that might legitimately mention the name.
    const blockTypesMatch = source.match(/const\s+BLOCK_TYPES\s*=\s*\[[\s\S]*?\]\s*as\s+const/);
    expect(
      blockTypesMatch,
      "BLOCK_TYPES array must be present in PaletteSidebar.tsx",
    ).not.toBeNull();

    const blockTypesSource = blockTypesMatch![0];
    expect(
      blockTypesSource,
      "BLOCK_TYPES must not contain a 'FileWriter' label — it was removed from the engine",
    ).not.toMatch(/FileWriter/);
  });

  it("BLOCK_TYPES does NOT reference FileOutput icon (used exclusively for FileWriter)", () => {
    const source = readSource(PALETTE_PATH);

    // FileOutput is the lucide icon imported solely for the FileWriter palette entry.
    // Once FileWriter is removed, this import and usage should also disappear.
    const blockTypesMatch = source.match(/const\s+BLOCK_TYPES\s*=\s*\[[\s\S]*?\]\s*as\s+const/);
    const blockTypesSource = blockTypesMatch ? blockTypesMatch[0] : "";

    expect(
      blockTypesSource,
      "BLOCK_TYPES must not reference FileOutput icon — FileWriter was removed",
    ).not.toMatch(/FileOutput/);
  });
});

// ===========================================================================
// 2. Palette — all entries map to valid engine block types (AC2)
// ===========================================================================

describe("PaletteSidebar — all BLOCK_TYPES entries are valid engine types (AC2)", () => {
  it("every BLOCK_TYPES label maps to a canonical StepType", () => {
    const source = readSource("features/surface/PaletteSidebar.tsx");

    // Extract labels from the BLOCK_TYPES array: `{ label: "Foo", ... }`
    const labelMatches = [...source.matchAll(/label:\s*["']([^"']+)["']/g)];
    const labels = labelMatches.map((m) => m[1]);

    expect(labels.length, "BLOCK_TYPES should have at least one entry").toBeGreaterThan(0);

    // Map UI display labels to their expected engine type names.
    // We allow a mapping (display → snake_case engine name) because the UI
    // may use title-case labels while the engine uses snake_case identifiers.
    const UI_LABEL_TO_ENGINE: Record<string, string> = {
      Linear: "linear",
      Gate: "gate",
      Code: "code",
      Dispatch: "dispatch",
      Synthesize: "synthesize",
      Workflow: "workflow",
      Loop: "loop",
      "Team Lead": "team_lead",
      "Engineering Manager": "engineering_manager",
      "HTTP Request": "http_request",
      // FileWriter intentionally omitted — it is NOT a valid engine type
    };

    for (const label of labels) {
      const engineType = UI_LABEL_TO_ENGINE[label];
      expect(
        engineType,
        `BLOCK_TYPES entry "${label}" has no corresponding canonical engine type — either it was removed or the mapping is missing`,
      ).toBeDefined();

      expect(
        CANONICAL_ENGINE_TYPES.has(engineType),
        `Engine type "${engineType}" (from palette label "${label}") is not in the canonical engine type list`,
      ).toBe(true);
    }
  });

  it("FileWriter label is not present anywhere in BLOCK_TYPES labels", () => {
    const source = readSource("features/surface/PaletteSidebar.tsx");

    const blockTypesMatch = source.match(/const\s+BLOCK_TYPES\s*=\s*\[[\s\S]*?\]\s*as\s+const/);
    const blockTypesSource = blockTypesMatch ? blockTypesMatch[0] : "";

    const labelMatches = [...blockTypesSource.matchAll(/label:\s*["']([^"']+)["']/g)];
    const labels = labelMatches.map((m) => m[1]);

    expect(
      labels,
      "FileWriter should not appear in BLOCK_TYPES labels",
    ).not.toContain("FileWriter");
  });
});

// ===========================================================================
// 3. WorkflowSurface drop handler — removed by main (canvas coming soon)
//    AC3 is moot — drag/drop was removed from WorkflowSurface in main.
//    When canvas ships and drag/drop returns, re-add validation tests.
// ===========================================================================

// ===========================================================================
// 4. yamlCompiler — unknown stepType must NOT silently default to "linear" (AC4)
// ===========================================================================

describe("yamlCompiler — rejects unknown stepType instead of defaulting to linear (AC4)", () => {
  it("does not emit type: linear for a node with no stepType", () => {
    // A node with undefined stepType must NOT silently become a linear block.
    // The compiler should throw, warn, or skip the node — anything but
    // producing { type: linear } as if the step were a valid linear block.
    const node = mockNode("no_type", undefined);

    let result: ReturnType<typeof compileOne> | undefined;
    let threw = false;

    try {
      result = compileOne(node);
    } catch {
      threw = true;
    }

    if (threw) {
      // Throwing is an acceptable rejection strategy.
      expect(threw).toBe(true);
      return;
    }

    // If the compiler did not throw it must not have silently produced "linear".
    const block = result!.block;
    expect(
      block?.type,
      "Compiler must not silently default a missing stepType to 'linear' — " +
        "received type: linear for a node with no stepType set",
    ).not.toBe("linear");
  });

  it("does not emit type: linear for a node with an unrecognised stepType", () => {
    // Dragging a removed/unknown block type should not silently become linear.
    const node = mockNode("bad_type", "FileWriter" as unknown as StepType);

    let result: ReturnType<typeof compileOne> | undefined;
    let threw = false;

    try {
      result = compileOne(node);
    } catch {
      threw = true;
    }

    if (threw) {
      expect(threw).toBe(true);
      return;
    }

    const block = result!.block;
    expect(
      block?.type,
      "Compiler must not silently coerce an unrecognised stepType ('FileWriter') to 'linear'",
    ).not.toBe("linear");
  });

  it("compiler source does not contain the bare ?? ('linear' as StepType) fallback", () => {
    // The literal silent-default pattern from yamlCompiler.ts:64 must be gone.
    const source = readSource("features/surface/yamlCompiler.ts");

    const hasSilentDefault =
      /\?\?\s*\(["']linear["']\s+as\s+StepType\)/.test(source) ||
      /\?\?\s*["']linear["']/.test(source);

    expect(
      hasSilentDefault,
      "yamlCompiler.ts still contains the silent `?? ('linear' as StepType)` fallback at line ~64 — this must be replaced with explicit validation or an error",
    ).toBe(false);
  });

  it("compiling a valid linear node still emits type: linear (regression guard)", () => {
    // Ensure the fix doesn't break legitimate linear blocks.
    const node = mockNode("step_a", "linear");
    const { block } = compileOne(node);
    expect(block.type).toBe("linear");
  });

  it("compiling a valid gate node still emits type: gate (regression guard)", () => {
    const node = mockNode("step_b", "gate");
    const { block } = compileOne(node);
    expect(block.type).toBe("gate");
  });

  it("compiling a valid code node still emits type: code (regression guard)", () => {
    const node = mockNode("step_c", "code");
    const { block } = compileOne(node);
    expect(block.type).toBe("code");
  });
});
