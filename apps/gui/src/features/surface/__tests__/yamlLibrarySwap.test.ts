/**
 * RED-TEAM tests for RUN-136: Switch YAML library from js-yaml to eemeli/yaml.
 *
 * Tests verify:
 * 1. YAML parsing works (string -> object) using the new library
 * 2. YAML stringifying works (object -> string) using the new library
 * 3. Comments are preserved on round-trip (the key motivation for the swap)
 * 4. No js-yaml imports remain in the source files
 * 5. Existing parse/compile behavior is unchanged
 *
 * Expected to FAIL against the current implementation (which still uses js-yaml).
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { compileGraphToWorkflowYaml } from "../yamlCompiler";
import { parseWorkflowYamlToGraph } from "../yamlParser";
import type { StepNodeData, StepType, SoulDef } from "../../../types/schemas/canvas";
import type { Node, Edge } from "@xyflow/react";

// ---------------------------------------------------------------------------
// Helpers
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

function mockEdge(source: string, target: string): Edge {
  return {
    id: `${source}->${target}`,
    source,
    target,
    sourceHandle: null,
    targetHandle: null,
  };
}

/** Read a source file relative to the canvas feature directory. */
function readSourceFile(relativePath: string): string {
  const canvasDir = resolve(__dirname, "..");
  return readFileSync(resolve(canvasDir, relativePath), "utf-8");
}

// ===========================================================================
// 1. No js-yaml imports remain in source files
// ===========================================================================

describe("No js-yaml imports in source files", () => {
  const sourceFiles = [
    "yamlCompiler.ts",
    "yamlParser.ts",
    "SurfaceCanvas.tsx",
  ];

  it.each(sourceFiles)(
    "%s does not import from js-yaml",
    (file) => {
      const content = readSourceFile(file);
      // Should NOT contain any import from "js-yaml"
      expect(content).not.toMatch(/from\s+["']js-yaml["']/);
      expect(content).not.toMatch(/require\s*\(\s*["']js-yaml["']\s*\)/);
    },
  );

  it("yamlCompiler uses YAML.stringify (from eemeli/yaml) instead of dump", () => {
    const content = readSourceFile("yamlCompiler.ts");
    // Should not use js-yaml's dump
    expect(content).not.toMatch(/\bdump\s*\(/);
    // Should import from "yaml" (the eemeli/yaml package)
    expect(content).toMatch(/from\s+["']yaml["']/);
  });

  it("yamlParser uses YAML.parse (from eemeli/yaml) instead of load", () => {
    const content = readSourceFile("yamlParser.ts");
    // Should not use js-yaml's load
    expect(content).not.toMatch(/\bload\s*\(/);
    // Should import from "yaml" (the eemeli/yaml package)
    expect(content).toMatch(/from\s+["']yaml["']/);
  });
});

// ===========================================================================
// 2. YAML parsing still works (string -> object)
// ===========================================================================

describe("YAML parsing works with new library", () => {
  it("parses a simple workflow YAML into nodes and edges", () => {
    const yamlText = `
version: "1.0"
blocks:
  step_a:
    type: linear
    soul_ref: researcher
  step_b:
    type: gate
    soul_ref: checker
    eval_key: ok
workflow:
  name: test
  entry: step_a
  transitions:
    - from: step_a
      to: step_b
`;
    const result = parseWorkflowYamlToGraph(yamlText);

    expect(result.error).toBeUndefined();
    expect(result.nodes).toHaveLength(2);
    expect(result.edges).toHaveLength(1);
    expect(result.nodes[0].data.stepType).toBe("linear");
    expect(result.nodes[0].data.soulRef).toBe("researcher");
    expect(result.nodes[1].data.stepType).toBe("gate");
  });

  it("returns error for invalid YAML", () => {
    const badYaml = `
blocks:
  step_a:
    type: linear
    nested:
      - broken: [
`;
    const result = parseWorkflowYamlToGraph(badYaml);
    expect(result.error).toBeDefined();
    expect(result.error!.message).toBeTruthy();
  });

  it("handles empty string input", () => {
    const result = parseWorkflowYamlToGraph("");
    expect(result.error).toBeUndefined();
    expect(result.nodes).toHaveLength(0);
  });

  it("parses config section with inline souls and emits no warning (RUN-748)", () => {
    const yamlText = `
version: "1.0"
config:
  max_concurrency: 4
souls:
  planner:
    id: planner
    role: planner
    system_prompt: You plan things.
blocks:
  step1:
    type: linear
    soul_ref: planner
workflow:
  name: test
  entry: step1
  transitions: []
`;
    const result = parseWorkflowYamlToGraph(yamlText);

    // RUN-748: inline souls are now valid — no deprecation warning should be emitted
    expect(result.error).toBeUndefined();
    expect(result.config).toBeDefined();
    expect(result.config!.max_concurrency).toBe(4);
  });
});

// ===========================================================================
// 3. YAML stringifying works (object -> string)
// ===========================================================================

describe("YAML stringifying works with new library", () => {
  it("compiles a graph to valid YAML string", () => {
    const nodes = [
      mockNode("step_a", "linear", { soulRef: "researcher" }),
      mockNode("step_b", "linear"),
    ];
    const edges = [mockEdge("step_a", "step_b")];

    const result = compileGraphToWorkflowYaml({ nodes, edges });

    expect(result.yaml).toBeTruthy();
    expect(typeof result.yaml).toBe("string");
    // The YAML should contain expected keys
    expect(result.yaml).toContain("version:");
    expect(result.yaml).toContain("blocks:");
    expect(result.yaml).toContain("workflow:");
    expect(result.yaml).toContain("step_a:");
    expect(result.yaml).toContain("soul_ref: researcher");
  });

  it("compiled YAML is parseable back into the same structure", () => {
    const nodes = [
      mockNode("a", "linear", { soulRef: "s1" }),
      mockNode("b", "dispatch", { soulRefs: ["x", "y"] }),
    ];
    const edges = [mockEdge("a", "b")];

    const compiled = compileGraphToWorkflowYaml({ nodes, edges });
    const parsed = parseWorkflowYamlToGraph(compiled.yaml);

    expect(parsed.error).toBeUndefined();
    expect(parsed.nodes).toHaveLength(2);
    expect(parsed.nodes[0].data.soulRef).toBe("s1");
    expect(parsed.nodes[1].data.soulRefs).toEqual(["x", "y"]);
  });
});

// ===========================================================================
// 4. Comment preservation on round-trip (KEY FEATURE)
// ===========================================================================

describe("YAML comment preservation", () => {
  it("preserves top-level comments on round-trip through parse and stringify", async () => {
    // This is the core reason for the library swap: js-yaml destroys comments.
    // The eemeli/yaml library can preserve them.
    //
    // We dynamically import "yaml" (eemeli/yaml) to test comment preservation
    // directly. If the library hasn't been installed, this test will fail.
    const YAML = await import("yaml");

    const yamlWithComments = `# This is the main workflow configuration
version: "1.0"

# Block definitions
blocks:
  step_a:
    type: linear
    soul_ref: researcher  # The research agent

# Workflow orchestration
workflow:
  name: test
  entry: step_a
  transitions: []
`;

    // Parse into a Document (preserves comments)
    const doc = YAML.parseDocument(yamlWithComments);
    // Stringify back
    const output = String(doc);

    // Comments should survive the round-trip
    expect(output).toContain("# This is the main workflow configuration");
    expect(output).toContain("# Block definitions");
    expect(output).toContain("# The research agent");
    expect(output).toContain("# Workflow orchestration");
  });

  it("preserves inline comments after modification", async () => {
    const YAML = await import("yaml");

    const yamlWithComments = `version: "1.0"
blocks:
  step_a:
    type: linear
    soul_ref: old_soul  # important agent
workflow:
  name: test
  entry: step_a
  transitions: []
`;

    const doc = YAML.parseDocument(yamlWithComments);

    // Modify a value while keeping the document structure
    const blocks = doc.get("blocks") as any;
    const stepA = blocks.get("step_a") as any;
    stepA.set("soul_ref", "new_soul");

    const output = String(doc);

    // The value should be updated
    expect(output).toContain("new_soul");
    // But comments should still be there
    expect(output).toContain("# important agent");
  });

  it("preserves multi-line comments in complex workflows", async () => {
    const YAML = await import("yaml");

    const complexYaml = `# =============================================================================
# Pipeline: Research & Synthesis
# Author: team@runsight.dev
# =============================================================================

version: "1.0"

# --- Agent Definitions ---
souls:
  researcher:
    id: researcher
    role: researcher
    system_prompt: You research topics.
    # TODO: Add tool access

# --- Block Definitions ---
blocks:
  # First step: research
  research:
    type: linear
    soul_ref: researcher

  # Second step: output
  output:
    type: file_writer
    output_path: ./report.md
    content_key: result

# --- Workflow ---
workflow:
  name: research-pipeline
  entry: research
  transitions:
    - from: research
      to: output
`;

    const doc = YAML.parseDocument(complexYaml);
    const output = String(doc);

    // All comment blocks should survive
    expect(output).toContain("# Pipeline: Research & Synthesis");
    expect(output).toContain("# Author: team@runsight.dev");
    expect(output).toContain("# --- Agent Definitions ---");
    expect(output).toContain("# TODO: Add tool access");
    expect(output).toContain("# First step: research");
    expect(output).toContain("# Second step: output");
    expect(output).toContain("# --- Workflow ---");
  });
});

// ===========================================================================
// 5. Existing parse/compile behavior is unchanged
// ===========================================================================

describe("Existing behavior unchanged after library swap", () => {
  it("full compile -> parse -> compile round-trip produces identical YAML (RUN-574: no souls)", () => {
    const nodes = [
      mockNode("plan", "linear", { soulRef: "planner" }),
      mockNode("execute", "dispatch", { soulRefs: ["planner"] }),
      mockNode("done", "linear"),
    ];
    const edges = [
      mockEdge("plan", "execute"),
      mockEdge("execute", "done"),
    ];

    const pass1 = compileGraphToWorkflowYaml({
      nodes,
      edges,
      workflowName: "round-trip-test",
    });

    const parsed = parseWorkflowYamlToGraph(pass1.yaml);
    expect(parsed.error).toBeUndefined();

    const pass2 = compileGraphToWorkflowYaml({
      nodes: parsed.nodes,
      edges: parsed.edges,
      workflowName: "round-trip-test",
    });

    // YAML output should be identical across both passes
    expect(pass2.yaml).toBe(pass1.yaml);
  });

  it("compiled YAML contains version field", () => {
    const result = compileGraphToWorkflowYaml({
      nodes: [mockNode("a", "linear")],
      edges: [],
    });

    expect(result.workflowDocument.version).toBe("1.0");
    expect(result.yaml).toContain("version:");
  });

  it("compiled YAML does not produce YAML aliases/anchors (noRefs equivalent)", () => {
    // js-yaml used { noRefs: true }; eemeli/yaml must also avoid aliases
    const sharedSoul: SoulDef = {
      id: "shared",
      role: "worker",
      system_prompt: "Shared prompt.",
    };

    const souls: Record<string, SoulDef> = {
      soul_a: sharedSoul,
      soul_b: sharedSoul,  // same reference
    };

    const result = compileGraphToWorkflowYaml({
      nodes: [mockNode("a", "linear", { soulRef: "soul_a" })],
      edges: [],
      souls,
    });

    // Should not contain YAML anchors or aliases
    expect(result.yaml).not.toMatch(/&\w+/);  // no anchors like &anchor
    expect(result.yaml).not.toMatch(/\*\w+/);  // no aliases like *alias
  });

  it("multiline strings are handled correctly in the new library", () => {
    const code = `def main():
    data = {"key": "value"}
    for k, v in data.items():
        print(f"{k}: {v}")
    return data`;

    const node = mockNode("code_block", "code", {
      code,
      timeoutSeconds: 30,
      allowedImports: ["json"],
    });

    const compiled = compileGraphToWorkflowYaml({ nodes: [node], edges: [] });
    const parsed = parseWorkflowYamlToGraph(compiled.yaml);

    expect(parsed.error).toBeUndefined();
    expect(parsed.nodes[0].data.code).toBe(code);
  });

  it("empty blocks and transitions compile and parse correctly", () => {
    const result = compileGraphToWorkflowYaml({ nodes: [], edges: [] });
    expect(result.yaml).toBeTruthy();

    const parsed = parseWorkflowYamlToGraph(result.yaml);
    expect(parsed.error).toBeUndefined();
    expect(parsed.nodes).toHaveLength(0);
  });
});
