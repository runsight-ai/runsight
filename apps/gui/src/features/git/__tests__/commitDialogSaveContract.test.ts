import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  defaultGitDiff,
  defaultWorkflowDraft,
  findCommitSaveButton,
  findElement,
  renderCommitDialogMarkup,
  renderCommitDialogTree,
  textContent,
} from "./commitDialogTestBuilders";

const mocks = vi.hoisted(() => ({
  stateValues: [] as unknown[],
  stateCursor: 0,
  workflowCommitMutate: vi.fn(),
  workflowCommitPending: false,
  genericCommitMutate: vi.fn(),
  gitDiffResult: {
    data: undefined,
    isLoading: false,
  } as { data?: { diff?: string }; isLoading: boolean },
}));

vi.mock("react", async () => {
  const actual = await vi.importActual<typeof React>("react");

  return {
    ...actual,
    useState: <T,>(initial: T | (() => T)) => {
      const index = mocks.stateCursor++;

      if (!(index in mocks.stateValues)) {
        mocks.stateValues[index] =
          typeof initial === "function" ? (initial as () => T)() : initial;
      }

      const setState = (value: T | ((previous: T) => T)) => {
        const previous = mocks.stateValues[index] as T;
        mocks.stateValues[index] =
          typeof value === "function"
            ? (value as (previous: T) => T)(previous)
            : value;
      };

      return [mocks.stateValues[index] as T, setState] as const;
    },
  };
});

vi.mock("@/queries/git", () => ({
  useCommit: () => ({
    mutate: mocks.genericCommitMutate,
    isPending: false,
  }),
  useCommitWorkflow: () => ({
    mutate: mocks.workflowCommitMutate,
    isPending: mocks.workflowCommitPending,
  }),
  useGitDiff: () => mocks.gitDiffResult,
}));

vi.mock("../DiffView", () => ({
  DiffView: (props: { draft?: { yaml?: string } }) => {
    if (mocks.gitDiffResult.isLoading) {
      return React.createElement("div", null, "Loading diff...");
    }

    if (mocks.gitDiffResult.data?.diff) {
      return React.createElement("pre", null, mocks.gitDiffResult.data.diff);
    }

    return React.createElement("pre", null, props.draft?.yaml ?? "");
  },
}));

vi.mock("@runsight/ui/dialog", () => ({
  Dialog: ({ open, children }: { open: boolean; children: React.ReactNode }) =>
    open ? React.createElement("div", null, children) : null,
  DialogContent: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", null, children),
  DialogHeader: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", null, children),
  DialogTitle: ({ children }: { children: React.ReactNode }) =>
    React.createElement("h2", null, children),
  DialogBody: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", null, children),
  DialogFooter: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", null, children),
}));

vi.mock("@runsight/ui/button", () => ({
  Button: (props: Record<string, unknown>) =>
    React.createElement("button", { type: "button", ...props }, props.children),
}));

const { CommitDialog } = await import("../CommitDialog");

function renderDialog(overrides: Record<string, unknown> = {}) {
  return renderCommitDialogTree(CommitDialog, mocks, overrides);
}

beforeEach(() => {
  mocks.stateValues.length = 0;
  mocks.stateCursor = 0;
  mocks.workflowCommitMutate.mockReset();
  mocks.workflowCommitPending = false;
  mocks.genericCommitMutate.mockReset();
  mocks.gitDiffResult = {
    data: defaultGitDiff,
    isLoading: false,
  };
});

describe("CommitDialog workflow save contract", () => {
  it("requires an editable commit message and routes save through the workflow commit mutation", () => {
    const initialTree = renderDialog();
    const messageInput = findElement(initialTree, (element) => element.type === "textarea");
    const saveButton = findCommitSaveButton(initialTree);

    expect(messageInput?.props.value).toBe("");
    expect(saveButton?.props.disabled).toBe(true);

    messageInput?.props.onChange?.({ target: { value: "  Save workflow to main  " } });

    const editedTree = renderDialog();
    const editedMessageInput = findElement(editedTree, (element) => element.type === "textarea");
    const enabledSaveButton = findCommitSaveButton(editedTree);

    expect(editedMessageInput?.props.value).toBe("  Save workflow to main  ");
    expect(enabledSaveButton?.props.disabled).toBe(false);

    enabledSaveButton?.props.onClick?.();

    const [variables, options] = mocks.workflowCommitMutate.mock.calls[0] ?? [];

    expect(mocks.genericCommitMutate).not.toHaveBeenCalled();
    expect(variables).toEqual({
      workflowId: "review_flow",
      payload: {
        yaml: "workflow:\n  name: Draft Flow\n",
        canvas_state: { nodes: [{ id: "draft-soul-node" }], edges: [] },
        message: "Save workflow to main",
      },
    });
    expect(options).toEqual(
      expect.objectContaining({
        onSuccess: expect.any(Function),
      }),
    );
  });

  it("shows a first-save preview of the current workflow when no diff against main exists yet", () => {
    mocks.gitDiffResult = {
      data: { diff: "" },
      isLoading: false,
    };

    const markup = renderCommitDialogMarkup(CommitDialog);

    expect(markup).toContain(defaultWorkflowDraft.yaml);
  });

  it("prevents duplicate submit while the workflow commit is pending", () => {
    mocks.workflowCommitPending = true;

    const pendingTree = renderDialog();

    const saveButton = findCommitSaveButton(pendingTree);

    expect(saveButton?.props.disabled).toBe(true);
    expect(textContent(saveButton)).toMatch(/saving|committing/i);
  });
});
