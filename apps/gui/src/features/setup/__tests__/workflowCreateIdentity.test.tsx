import { afterEach, describe, expect, it, vi } from "vitest";
import { parse } from "yaml";

import {
  DEFAULT_WORKFLOW_NAME,
  buildBlankWorkflowCreate,
  buildBlankWorkflowYaml,
  deriveWorkflowId,
  isValidWorkflowId,
} from "../workflowDraft";

describe("setup workflow identity verification", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("derives a valid editable workflow id from the default name", () => {
    const derived = deriveWorkflowId(DEFAULT_WORKFLOW_NAME);

    expect(derived).toBe("untitled-workflow");
    expect(isValidWorkflowId(derived)).toBe(true);
    expect(isValidWorkflowId("123")).toBe(false);
    expect(isValidWorkflowId("workflow-")).toBe(false);
  });

  it("buildBlankWorkflowYaml emits embedded workflow identity", () => {
    const workflowId = "custom-workflow";
    const yaml = buildBlankWorkflowYaml(workflowId, "Custom Workflow");
    const parsed = parse(yaml) as Record<string, unknown>;

    expect(parsed.id).toBe(workflowId);
    expect(parsed.kind).toBe("workflow");
    expect(yaml).toContain(workflowId);
    expect(parsed.enabled).toBe(false);
    expect(parsed.blocks).toEqual({});
    expect(parsed.workflow).toEqual({
      name: "Custom Workflow",
      entry: "start",
      transitions: [],
    });
  });

  it("buildBlankWorkflowCreate generates distinct draft identities for repeated creates", () => {
    vi.spyOn(Date, "now")
      .mockReturnValueOnce(1730000000000)
      .mockReturnValueOnce(1730000001000);
    vi.spyOn(Math, "random")
      .mockReturnValueOnce(0.123456789)
      .mockReturnValueOnce(0.987654321);

    const firstCreate = buildBlankWorkflowCreate();
    const secondCreate = buildBlankWorkflowCreate();

    const firstDraft = parse(firstCreate.yaml) as Record<string, unknown>;
    const secondDraft = parse(secondCreate.yaml) as Record<string, unknown>;

    expect(firstDraft.id).toBeTruthy();
    expect(secondDraft.id).toBeTruthy();
    expect(firstDraft.kind).toBe("workflow");
    expect(secondDraft.kind).toBe("workflow");
    expect(firstDraft.id).not.toBe("untitled-workflow");
    expect(secondDraft.id).not.toBe("untitled-workflow");
    expect(firstDraft.id).not.toEqual(secondDraft.id);

    expect(firstCreate.yaml).toContain(String(firstDraft.id));
    expect(secondCreate.yaml).toContain(String(secondDraft.id));
    expect(firstCreate.name).toBe(DEFAULT_WORKFLOW_NAME);
    expect(secondCreate.name).toBe(DEFAULT_WORKFLOW_NAME);
    expect(firstCreate.commit).toBe(false);
    expect(secondCreate.commit).toBe(false);
  });
});
