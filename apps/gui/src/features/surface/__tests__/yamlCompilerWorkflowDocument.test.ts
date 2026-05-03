import { describe, expect, it } from "vitest";
import { compileGraphToWorkflowYaml } from "../yamlCompiler";
import type { SoulDef } from "../../../types/schemas/canvas";
import { compileOne, mockNode } from "./helpers/yamlCompilerFixtures";

describe("CompiledWorkflow blocks use full BlockDef shape", () => {
  it("blocks record contains fully typed BlockDef objects", () => {
    const node = mockNode("b1", "gate", {
      soulRef: "gatekeeper",
      evalKey: "quality",
      extractField: "score",
    });
    const { doc } = compileOne(node);
    const block = doc.blocks["b1"];

    // Should have more than just `type`
    expect(Object.keys(block).length).toBeGreaterThan(1);
    expect(block).toHaveProperty("soul_ref");
    expect(block).toHaveProperty("eval_key");
    expect(block).toHaveProperty("extract_field");
  });

  it("YAML output contains snake_case field keys within blocks", () => {
    const node = mockNode("b1", "gate", {
      soulRef: "gatekeeper",
      evalKey: "quality",
      extractField: "score",
    });
    const { yaml } = compileOne(node);

    // snake_case keys in YAML
    expect(yaml).toContain("soul_ref:");
    expect(yaml).toContain("eval_key:");
    expect(yaml).toContain("extract_field:");

    // camelCase should NOT appear
    expect(yaml).not.toContain("soulRef:");
    expect(yaml).not.toContain("evalKey:");
  });

  it("multiple nodes each emit their own typed fields", () => {
    const nodes = [
      mockNode("linear1", "linear", { soulRef: "s1" }),
      mockNode("code1", "code", { code: "x=1", timeoutSeconds: 30 }),
      mockNode("gate1", "gate", {
        soulRef: "gs",
        evalKey: "ok",
        extractField: "val",
      }),
    ];
    const result = compileGraphToWorkflowYaml({ nodes, edges: [] });
    const blocks = result.workflowDocument.blocks;

    expect(blocks["linear1"]).toEqual({ type: "linear", soul_ref: "s1" });
    expect(blocks["code1"]).toEqual({
      type: "code",
      code: "x=1",
      timeout_seconds: 30,
    });
    expect(blocks["gate1"]).toEqual({
      type: "gate",
      soul_ref: "gs",
      eval_key: "ok",
      extract_field: "val",
    });
  });
});

describe("Souls and config top-level sections", () => {
  const sampleSouls: Record<string, SoulDef> = {
    planner: {
      id: "planner",
      role: "planner",
      system_prompt: "You are a planning agent.",
    },
  };

  const sampleConfig: Record<string, unknown> = {
    max_concurrency: 4,
    timeout: 300,
  };

  it("souls are NOT included in compiled output even when provided", () => {
    const result = compileGraphToWorkflowYaml({
      nodes: [mockNode("b1", "linear", { soulRef: "planner" })],
      edges: [],
      souls: sampleSouls,
    });
    expect(result.workflowDocument).not.toHaveProperty("souls");
  });

  it("config is included in compiled output when provided", () => {
    const result = compileGraphToWorkflowYaml({
      nodes: [mockNode("b1", "linear", { soulRef: "s1" })],
      edges: [],
      config: sampleConfig,
    });
    expect(result.workflowDocument.config).toEqual(sampleConfig);
  });

  it("souls do NOT appear in YAML string output even when provided", () => {
    const result = compileGraphToWorkflowYaml({
      nodes: [mockNode("b1", "linear", { soulRef: "planner" })],
      edges: [],
      souls: sampleSouls,
    });
    expect(result.yaml).not.toMatch(/^souls:/m);
  });

  it("config appears in YAML string output", () => {
    const result = compileGraphToWorkflowYaml({
      nodes: [mockNode("b1", "linear", { soulRef: "s1" })],
      edges: [],
      config: sampleConfig,
    });
    expect(result.yaml).toContain("config:");
    expect(result.yaml).toContain("max_concurrency: 4");
    expect(result.yaml).toContain("timeout: 300");
  });

  it("empty souls object is omitted", () => {
    const result = compileGraphToWorkflowYaml({
      nodes: [mockNode("b1", "linear")],
      edges: [],
      souls: {},
    });
    expect(result.workflowDocument).not.toHaveProperty("souls");
    expect(result.yaml).not.toContain("souls:");
  });

  it("empty config object is omitted", () => {
    const result = compileGraphToWorkflowYaml({
      nodes: [mockNode("b1", "linear")],
      edges: [],
      config: {},
    });
    expect(result.workflowDocument.config).toBeUndefined();
    expect(result.yaml).not.toContain("config:");
  });

  it("undefined souls/config are omitted", () => {
    const result = compileGraphToWorkflowYaml({
      nodes: [mockNode("b1", "linear")],
      edges: [],
    });
    expect(result.workflowDocument).not.toHaveProperty("souls");
    expect(result.workflowDocument.config).toBeUndefined();
    expect(result.yaml).not.toContain("souls:");
    expect(result.yaml).not.toContain("config:");
  });

  it("soul fields are NOT serialized to top-level souls section", () => {
    const fullSoul: SoulDef = {
      id: "coder",
      role: "engineer",
      system_prompt: "You write code.",
      tools: [{ name: "file_read", config: { root: "/src" } }],
      model_name: "claude-3-opus",
    };
    const result = compileGraphToWorkflowYaml({
      nodes: [mockNode("b1", "linear", { soulRef: "coder" })],
      edges: [],
      souls: { coder: fullSoul },
    });
    // Souls are never emitted in the compiled output.
    expect(result.workflowDocument).not.toHaveProperty("souls");
    expect(result.yaml).not.toMatch(/^souls:/m);
    // But soul_ref on blocks should still work
    expect(result.workflowDocument.blocks["b1"]).toHaveProperty("soul_ref", "coder");
  });

  it("config with nested objects serializes correctly", () => {
    const nestedConfig: Record<string, unknown> = {
      retry_policy: {
        max_retries: 3,
        backoff: { type: "exponential", base_ms: 100 },
      },
      logging: { level: "debug" },
    };
    const result = compileGraphToWorkflowYaml({
      nodes: [mockNode("b1", "linear")],
      edges: [],
      config: nestedConfig,
    });
    expect(result.workflowDocument.config).toEqual(nestedConfig);
    expect(result.yaml).toContain("retry_policy:");
    expect(result.yaml).toContain("max_retries: 3");
    expect(result.yaml).toContain("type: exponential");
    expect(result.yaml).toContain("base_ms: 100");
    expect(result.yaml).toContain("level: debug");
  });
});
