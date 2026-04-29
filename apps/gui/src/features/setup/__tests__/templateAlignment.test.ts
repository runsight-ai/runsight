import { describe, it, expect } from "vitest";
import { parse } from "yaml";
import { TEMPLATE_YAML } from "../constants";

function parseTemplate(): Record<string, any> {
  return parse(TEMPLATE_YAML) as Record<string, any>;
}

describe("onboarding template alignment", () => {
  it("uses inline souls instead of library soul files", () => {
    expect(TEMPLATE_YAML).toMatch(/^souls:/m);
    expect(TEMPLATE_YAML).toMatch(/^\s+system_prompt:/m);
    expect(TEMPLATE_YAML).not.toMatch(/soul_ref:\s*writer/);
  });

  it("references only the inline souls used by the starter flow", () => {
    expect(TEMPLATE_YAML).toMatch(/soul_ref:\s*researcher/);
    expect(TEMPLATE_YAML).toMatch(/soul_ref:\s*reviewer/);
    expect(TEMPLATE_YAML).toMatch(/soul_ref:\s*error_writer/);
    expect(TEMPLATE_YAML.match(/soul_ref:/g) ?? []).toHaveLength(3);
  });

  it("whitelists file_io on the workflow and requires it in the two writer souls", () => {
    const parsed = parseTemplate();
    expect(parsed.tools).toEqual(["file_io"]);
    expect(parsed.souls?.researcher?.required_tool_calls).toEqual(["file_io"]);
    expect(parsed.souls?.error_writer?.required_tool_calls).toEqual(["file_io"]);
  });

  it("keeps the template artifact-first by targeting custom/outputs", () => {
    expect(TEMPLATE_YAML).toContain("custom/outputs/onboarding-research-brief.md");
    expect(TEMPLATE_YAML).toContain("custom/outputs/onboarding-research-error.md");
  });

  it("contains loud provider/model placeholders so users know config is required", () => {
    expect(TEMPLATE_YAML).toContain("PLACEHOLDER_PROVIDER_ID");
    expect(TEMPLATE_YAML).toContain("PLACEHOLDER_MODEL_NAME");
    expect(TEMPLATE_YAML).toContain("REQUIRED BEFORE RUNNING");
  });
});
