import { describe, it, expect } from "vitest";
import { parse } from "yaml";
import { parseWorkflowYamlToGraph } from "@/features/surface/yamlParser";
import { TEMPLATE_YAML } from "../constants";

function parseTemplate(): Record<string, any> {
  return parse(TEMPLATE_YAML) as Record<string, any>;
}

describe("TEMPLATE_YAML export", () => {
  it("is a non-empty workflow YAML string", () => {
    expect(typeof TEMPLATE_YAML).toBe("string");
    expect(TEMPLATE_YAML.length).toBeGreaterThan(0);
    expect(TEMPLATE_YAML).toMatch(/version:\s*['"]?1\.0['"]?/);
  });
});

describe("TEMPLATE_YAML flow-level wiring", () => {
  it("declares file_io once at the workflow level", () => {
    const parsed = parseTemplate();
    expect(parsed.tools).toEqual(["file_io"]);
  });

  it("defines inline souls for research, review, and fallback writing", () => {
    const parsed = parseTemplate();
    expect(Object.keys(parsed.souls ?? {})).toEqual([
      "researcher",
      "reviewer",
      "error_writer",
    ]);
  });

  it("only grants file_io to the inline souls that need to write files", () => {
    const parsed = parseTemplate();
    expect(parsed.souls?.researcher?.tools).toEqual(["file_io"]);
    expect(parsed.souls?.researcher?.required_tool_calls).toEqual(["file_io"]);
    expect(parsed.souls?.error_writer?.tools).toEqual(["file_io"]);
    expect(parsed.souls?.error_writer?.required_tool_calls).toEqual(["file_io"]);
    expect(parsed.souls?.reviewer?.tools).toBeUndefined();
  });

  it("uses explicit provider/model placeholders instead of shipping runnable defaults", () => {
    const parsed = parseTemplate();
    expect(parsed.souls?.researcher?.provider).toBe("PLACEHOLDER_PROVIDER_ID");
    expect(parsed.souls?.researcher?.model_name).toBe("PLACEHOLDER_MODEL_NAME");
    expect(parsed.souls?.researcher?.temperature).toBe(1);
    expect(parsed.souls?.reviewer?.provider).toBe("PLACEHOLDER_PROVIDER_ID");
    expect(parsed.souls?.reviewer?.model_name).toBe("PLACEHOLDER_MODEL_NAME");
    expect(parsed.souls?.reviewer?.temperature).toBe(1);
    expect(parsed.souls?.error_writer?.provider).toBe("PLACEHOLDER_PROVIDER_ID");
    expect(parsed.souls?.error_writer?.model_name).toBe("PLACEHOLDER_MODEL_NAME");
    expect(parsed.souls?.error_writer?.temperature).toBe(1);
  });
});

describe("TEMPLATE_YAML block graph", () => {
  it("defines the expected onboarding starter blocks", () => {
    const parsed = parseTemplate();
    expect(Object.keys(parsed.blocks ?? {})).toEqual([
      "draft_report",
      "quality_gate",
      "review_loop",
      "check_review_status",
      "write_error_stub",
      "finish_success",
      "finish_error",
    ]);
  });

  it("puts the researcher and gate inside a loop with retry semantics", () => {
    const parsed = parseTemplate();
    expect(parsed.blocks?.review_loop).toMatchObject({
      type: "loop",
      inner_block_refs: ["draft_report", "quality_gate"],
      max_rounds: 2,
      break_on_exit: "pass",
      retry_on_exit: "fail",
      error_route: "write_error_stub",
    });
    expect(parsed.blocks?.review_loop?.carry_context).toMatchObject({
      enabled: true,
      mode: "all",
      source_blocks: ["draft_report", "quality_gate"],
      inject_as: "previous_round_context",
    });
  });

  it("branches through review status before choosing finish vs error stub", () => {
    const parsed = parseTemplate();
    expect(parsed.workflow).toMatchObject({
      name: "Research & Review",
      entry: "review_loop",
    });
    expect(parsed.workflow?.transitions).toEqual([
      { from: "review_loop", to: "check_review_status" },
      { from: "write_error_stub", to: "finish_error" },
    ]);
    expect(parsed.workflow?.conditional_transitions).toEqual([
      {
        from: "check_review_status",
        pass: "finish_success",
        fail: "write_error_stub",
        default: "write_error_stub",
      },
    ]);
  });

  it("declares local inputs for CodeBlocks that consume upstream context", () => {
    const parsed = parseTemplate();
    expect(parsed.blocks?.check_review_status?.inputs).toEqual({
      loop_status: { from: "shared_memory.__loop__review_loop" },
    });
    expect(parsed.blocks?.finish_success?.inputs).toEqual({
      review_status_result: { from: "check_review_status" },
    });
    expect(parsed.blocks?.finish_error?.inputs).toEqual({
      review_status_result: { from: "check_review_status" },
      error_stub_result: { from: "write_error_stub" },
    });

    const broadReads = ["shared_memory", "results", "metadata"].map(
      (name) => `data["${name}"]`,
    );
    for (const block of Object.values(parsed.blocks ?? {}) as Array<Record<string, any>>) {
      if (block.type !== "code" || typeof block.code !== "string") {
        continue;
      }
      for (const broadRead of broadReads) {
        expect(block.code).not.toContain(broadRead);
      }
    }
  });

  it("declares success and fallback artifact paths in the template", () => {
    expect(TEMPLATE_YAML).toContain("custom/outputs/onboarding-research-brief.md");
    expect(TEMPLATE_YAML).toContain("custom/outputs/onboarding-research-error.md");
  });
});

describe("TEMPLATE_YAML parses in the canvas graph", () => {
  it("produces seven nodes with no parser error", () => {
    const result = parseWorkflowYamlToGraph(TEMPLATE_YAML);
    expect(result.error).toBeUndefined();
    expect(result.nodes.map((node) => node.id)).toEqual([
      "draft_report",
      "quality_gate",
      "review_loop",
      "check_review_status",
      "write_error_stub",
      "finish_success",
      "finish_error",
    ]);
  });
});
