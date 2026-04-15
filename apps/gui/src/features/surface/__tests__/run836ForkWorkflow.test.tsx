// @vitest-environment jsdom

import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { parse } from "yaml";

const harness = vi.hoisted(() => ({
  getGitFile: vi.fn(),
  createWorkflow: vi.fn(),
  generateForkName: vi.fn(() => "drft-source-workflow-a3f1"),
}));

vi.mock("@/api/git", () => ({
  gitApi: {
    getGitFile: harness.getGitFile,
  },
}));

vi.mock("@/api/workflows", () => ({
  workflowsApi: {
    createWorkflow: harness.createWorkflow,
  },
}));

vi.mock("../forkUtils", () => ({
  generateForkName: harness.generateForkName,
}));

import { useForkWorkflow } from "../../surface/useForkWorkflow";

const sourceWorkflowYaml = `
version: "1.0"
id: source-workflow
kind: workflow
enabled: true
blocks:
  child:
    type: workflow
    workflow_ref: nested-child
workflow:
  name: Source Workflow
  entry: child
  transitions:
    - from: child
      to: null
`;

beforeEach(() => {
  harness.getGitFile.mockReset();
  harness.createWorkflow.mockReset();
  harness.generateForkName.mockClear();
  harness.getGitFile.mockResolvedValue({
    content: sourceWorkflowYaml,
  });
  harness.createWorkflow.mockResolvedValue({ id: "wf_forked_836" });
  vi.stubGlobal("requestAnimationFrame", ((cb: FrameRequestCallback) => {
    cb(0);
    return 0;
  }) as typeof requestAnimationFrame);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

it("rewrites the forked workflow YAML to a fresh embedded id and draft name", async () => {
  const onTransition = vi.fn();
  const { result } = renderHook(() =>
    useForkWorkflow({
      commitSha: "commit_836",
      workflowPath: "custom/workflows/source-workflow.yaml",
      workflowName: "Source Workflow",
      onTransition,
    }),
  );

  act(() => {
    result.current.forkWorkflow();
  });

  await waitFor(() => {
    expect(harness.createWorkflow).toHaveBeenCalledWith({
      name: "drft-source-workflow-a3f1",
      yaml: expect.any(String),
      commit: false,
    });
  });

  const [{ yaml, name, commit }] = harness.createWorkflow.mock.calls[0];
  const parsedYaml = parse(yaml as string) as Record<string, unknown>;

  expect(name).toBe("drft-source-workflow-a3f1");
  expect(commit).toBe(false);
  expect(parsedYaml.id).toBe("drft-source-workflow-a3f1");
  expect(parsedYaml.kind).toBe("workflow");
  expect((parsedYaml.workflow as Record<string, unknown>).name).toBe(
    "drft-source-workflow-a3f1",
  );
  expect(parsedYaml.enabled).toBe(false);
  expect((parsedYaml.blocks as Record<string, Record<string, unknown>>).child.workflow_ref).toBe(
    "nested-child",
  );
  expect(onTransition).toHaveBeenCalledWith("wf_forked_836");
});
