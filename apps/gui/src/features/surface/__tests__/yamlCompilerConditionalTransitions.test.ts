import { describe, expect, it } from "vitest";
import { compileGraphToWorkflowYaml } from "../yamlCompiler";
import {
  mockEdge,
  mockNode,
  mockNodeWithConditions,
} from "./helpers/yamlCompilerFixtures";

describe("Conditional transitions compilation", () => {
  it("edges from node with output_conditions go into conditional_transitions, not transitions", () => {
    const nodes = [
      mockNodeWithConditions("decision", "linear", ["approved", "rejected", "default"]),
      mockNode("approve_step", "linear", { soulRef: "s1" }),
      mockNode("reject_step", "linear", { soulRef: "s2" }),
    ];
    const edges = [
      mockEdge("decision", "approve_step", "approved"),
      mockEdge("decision", "reject_step", "rejected"),
    ];
    const result = compileGraphToWorkflowYaml({ nodes, edges });
    const wf = result.workflowDocument.workflow as Record<string, unknown>;

    // Should appear in conditional_transitions
    expect(wf.conditional_transitions).toBeDefined();
    expect((wf.conditional_transitions as unknown[]).length).toBeGreaterThanOrEqual(1);

    // Should NOT appear in plain transitions
    const transitions = wf.transitions as Array<{ from: string; to: string }>;
    const plainFromDecision = transitions.filter((t) => t.from === "decision");
    expect(plainFromDecision).toHaveLength(0);
  });

  it("edges from node WITHOUT output_conditions stay in transitions", () => {
    const nodes = [
      mockNode("step_a", "linear", { soulRef: "s1" }),
      mockNode("step_b", "linear", { soulRef: "s2" }),
    ];
    const edges = [mockEdge("step_a", "step_b")];
    const result = compileGraphToWorkflowYaml({ nodes, edges });
    const wf = result.workflowDocument.workflow as Record<string, unknown>;

    expect(wf.transitions).toEqual([{ from: "step_a", to: "step_b" }]);
    expect(wf.conditional_transitions).toBeUndefined();
  });

  it("mixed: some edges conditional, some plain — correctly separated", () => {
    const nodes = [
      mockNode("plain_start", "linear", { soulRef: "s0" }),
      mockNodeWithConditions("decision", "gate", ["pass", "fail", "default"]),
      mockNode("pass_step", "linear", { soulRef: "s1" }),
      mockNode("fail_step", "linear", { soulRef: "s2" }),
      mockNode("fallback", "linear"),
    ];
    const edges = [
      mockEdge("plain_start", "decision"),          // plain
      mockEdge("decision", "pass_step", "pass"),    // conditional
      mockEdge("decision", "fail_step", "fail"),    // conditional
      mockEdge("decision", "fallback"),              // default (no sourceHandle)
    ];
    const result = compileGraphToWorkflowYaml({ nodes, edges });
    const wf = result.workflowDocument.workflow as Record<string, unknown>;

    // Plain transition
    expect(wf.transitions).toEqual([{ from: "plain_start", to: "decision" }]);

    // Conditional transitions
    expect(wf.conditional_transitions).toBeDefined();
    const ctArray = wf.conditional_transitions as Record<string, string>[];
    expect(ctArray.length).toBe(1);
    const ct = ctArray[0];
    expect(ct.from).toBe("decision");
    expect(ct["pass"]).toBe("pass_step");
    expect(ct["fail"]).toBe("fail_step");
    expect(ct["default"]).toBe("fallback");
  });

  it("sourceHandle maps to decision key in conditional_transitions", () => {
    const nodes = [
      mockNodeWithConditions("decider", "linear", ["yes", "no"]),
      mockNode("yes_target", "linear"),
      mockNode("no_target", "linear"),
    ];
    const edges = [
      mockEdge("decider", "yes_target", "yes"),
      mockEdge("decider", "no_target", "no"),
    ];
    const result = compileGraphToWorkflowYaml({ nodes, edges });
    const wf = result.workflowDocument.workflow as Record<string, unknown>;
    const ct = wf.conditional_transitions as Record<string, string>[];

    expect(ct).toBeDefined();
    expect(ct.length).toBe(1);
    expect(ct[0].from).toBe("decider");
    expect(ct[0]["yes"]).toBe("yes_target");
    expect(ct[0]["no"]).toBe("no_target");
  });

  it("edge without sourceHandle from conditioned node maps to default", () => {
    const nodes = [
      mockNodeWithConditions("decider", "linear", ["option_a", "default"]),
      mockNode("a_target", "linear"),
      mockNode("fallback_target", "linear"),
    ];
    const edges = [
      mockEdge("decider", "a_target", "option_a"),
      mockEdge("decider", "fallback_target"),          // no sourceHandle → default
    ];
    const result = compileGraphToWorkflowYaml({ nodes, edges });
    const wf = result.workflowDocument.workflow as Record<string, unknown>;
    const ct = wf.conditional_transitions as Record<string, string>[];

    expect(ct).toBeDefined();
    expect(ct[0]["default"]).toBe("fallback_target");
    expect(ct[0]["option_a"]).toBe("a_target");
  });

  it("multiple conditional edges from same source grouped into one entry", () => {
    const nodes = [
      mockNodeWithConditions("src", "linear", ["a", "b", "c", "default"]),
      mockNode("t_a", "linear"),
      mockNode("t_b", "linear"),
      mockNode("t_c", "linear"),
      mockNode("t_default", "linear"),
    ];
    const edges = [
      mockEdge("src", "t_a", "a"),
      mockEdge("src", "t_b", "b"),
      mockEdge("src", "t_c", "c"),
      mockEdge("src", "t_default"),           // default
    ];
    const result = compileGraphToWorkflowYaml({ nodes, edges });
    const wf = result.workflowDocument.workflow as Record<string, unknown>;
    const ct = wf.conditional_transitions as Record<string, string>[];

    // All four edges should be grouped into a single entry
    expect(ct).toHaveLength(1);
    expect(ct[0].from).toBe("src");
    expect(ct[0]["a"]).toBe("t_a");
    expect(ct[0]["b"]).toBe("t_b");
    expect(ct[0]["c"]).toBe("t_c");
    expect(ct[0]["default"]).toBe("t_default");
  });

  it("conditional_transitions section omitted when no conditional edges exist", () => {
    const nodes = [
      mockNode("s1", "linear", { soulRef: "soul1" }),
      mockNode("s2", "linear", { soulRef: "soul2" }),
    ];
    const edges = [mockEdge("s1", "s2")];
    const result = compileGraphToWorkflowYaml({ nodes, edges });
    const wf = result.workflowDocument.workflow as Record<string, unknown>;

    expect(wf.conditional_transitions).toBeUndefined();
    expect(result.yaml).not.toContain("conditional_transitions");
  });

  it("output_conditions on block still emitted in blocks section", () => {
    const nodes = [
      mockNodeWithConditions("decider", "linear", ["yes", "no", "default"]),
      mockNode("target", "linear"),
    ];
    const edges = [mockEdge("decider", "target", "yes")];
    const result = compileGraphToWorkflowYaml({ nodes, edges });

    // Block should still have output_conditions
    const block = result.workflowDocument.blocks["decider"];
    expect(block.output_conditions).toBeDefined();
    expect(block.output_conditions).toHaveLength(3);
    expect(block.output_conditions!.map((c) => c.case_id)).toEqual(["yes", "no", "default"]);
  });

  it("node with output_conditions but no outgoing edges — no conditional_transition entry", () => {
    const nodes = [
      mockNodeWithConditions("orphan", "linear", ["a", "b", "default"]),
    ];
    const result = compileGraphToWorkflowYaml({ nodes, edges: [] });
    const wf = result.workflowDocument.workflow as Record<string, unknown>;

    // No edges → no conditional_transitions section
    expect(wf.conditional_transitions).toBeUndefined();
  });

  it("YAML string contains conditional_transitions section", () => {
    const nodes = [
      mockNodeWithConditions("decision_block", "linear", ["approved", "rejected", "default"]),
      mockNode("approve_block", "linear"),
      mockNode("reject_block", "linear"),
      mockNode("fallback_block", "linear"),
    ];
    const edges = [
      mockEdge("decision_block", "approve_block", "approved"),
      mockEdge("decision_block", "reject_block", "rejected"),
      mockEdge("decision_block", "fallback_block"),   // default
    ];
    const result = compileGraphToWorkflowYaml({ nodes, edges });

    expect(result.yaml).toContain("conditional_transitions:");
    expect(result.yaml).toContain("from: decision_block");
    expect(result.yaml).toContain("approved: approve_block");
    expect(result.yaml).toContain("rejected: reject_block");
    expect(result.yaml).toContain("default: fallback_block");
  });
});
