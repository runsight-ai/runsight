import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";
import { parse } from "yaml";

import {
  DEFAULT_WORKFLOW_NAME,
  buildBlankWorkflowYaml,
  deriveWorkflowId,
  isValidWorkflowId,
} from "../workflowDraft";

const SETUP_START_PAGE_PATH = resolve(__dirname, "..", "SetupStartPage.tsx");

function readSetupStartPageSource(): string {
  return readFileSync(SETUP_START_PAGE_PATH, "utf-8");
}

describe("RUN-834 setup workflow identity verification", () => {
  it("derives a valid editable workflow id from the default name", () => {
    const derived = deriveWorkflowId(DEFAULT_WORKFLOW_NAME);

    expect(derived).toBe("untitled-workflow");
    expect(isValidWorkflowId(derived)).toBe(true);
    expect(isValidWorkflowId("123")).toBe(false);
    expect(isValidWorkflowId("workflow-")).toBe(false);
  });

  it("buildBlankWorkflowYaml emits embedded workflow identity", () => {
    const yaml = buildBlankWorkflowYaml("custom-workflow", "Custom Workflow");
    const parsed = parse(yaml) as Record<string, unknown>;

    expect(parsed.id).toBe("custom-workflow");
    expect(parsed.kind).toBe("workflow");
    expect(parsed.enabled).toBe(false);
    expect(parsed.blocks).toEqual({});
    expect(parsed.workflow).toEqual({
      name: "Custom Workflow",
      entry: "start",
      transitions: [],
    });
  });

  it("wires the blank-create form to embedded ids and result-based navigation", () => {
    const source = readSetupStartPageSource();

    expect(source).toContain("workflowIdTouched");
    expect(source).toContain("buildBlankWorkflowYaml(normalizedWorkflowId, name)");
    expect(source).toContain('Label htmlFor="workflow-id"');
    expect(source).toContain('id="workflow-id"');
    expect(source).toContain("setWorkflowIdTouched(true)");
    expect(source).toContain("navigate(`/workflows/${result.id}/edit`, { replace: true })");
  });
});
