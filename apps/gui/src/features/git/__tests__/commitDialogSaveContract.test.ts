import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  stateValues: [] as unknown[],
  stateCursor: 0,
  workflowCommitMutate: vi.fn(),
  workflowCommitPending: false,
  genericCommitMutate: vi.fn(),
  gitDiffResult: {
    data: { diff: "diff --git a/custom/workflows/wf_1.yaml b/custom/workflows/wf_1.yaml" },
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
  mocks.stateCursor = 0;

  return (
    CommitDialog as unknown as (props: Record<string, unknown>) => React.ReactElement | null
  )({
    open: true,
    onOpenChange: vi.fn(),
    onCommitSuccess: vi.fn(),
    files: [{ path: "custom/workflows/wf_1.yaml", status: "A" }],
    workflowId: "wf_1",
    draft: {
      yaml: "workflow:\n  name: Draft Flow\n",
      canvas_state: { nodes: [{ id: "node-1" }], edges: [] },
    },
    ...overrides,
  });
}

function textContent(node: React.ReactNode): string {
  if (node == null || typeof node === "boolean") {
    return "";
  }

  if (typeof node === "string" || typeof node === "number") {
    return String(node);
  }

  if (!React.isValidElement(node)) {
    return "";
  }

  return React.Children.toArray(node.props.children).map(textContent).join("");
}

function findElement(
  node: React.ReactNode,
  predicate: (element: React.ReactElement) => boolean,
): React.ReactElement | undefined {
  if (!React.isValidElement(node)) {
    return undefined;
  }

  if (predicate(node)) {
    return node;
  }

  for (const child of React.Children.toArray(node.props.children)) {
    const match = findElement(child, predicate);
    if (match) {
      return match;
    }
  }

  return undefined;
}

beforeEach(() => {
  mocks.stateValues.length = 0;
  mocks.stateCursor = 0;
  mocks.workflowCommitMutate.mockReset();
  mocks.workflowCommitPending = false;
  mocks.genericCommitMutate.mockReset();
  mocks.gitDiffResult = {
    data: { diff: "diff --git a/custom/workflows/wf_1.yaml b/custom/workflows/wf_1.yaml" },
    isLoading: false,
  };
});

describe("CommitDialog workflow save contract (RUN-424)", () => {
  it("requires an editable commit message and routes save through the workflow commit mutation", () => {
    const initialTree = renderDialog();
    const messageInput = findElement(initialTree, (element) => element.type === "textarea");
    const saveButton = findElement(
      initialTree,
      (element) =>
        typeof element.props.onClick === "function" &&
        ["Commit", "Save", "Committing...", "Saving..."].includes(textContent(element)),
    );

    expect(messageInput?.props.value).toBe("");
    expect(saveButton?.props.disabled).toBe(true);

    messageInput?.props.onChange?.({ target: { value: "  Save workflow to main  " } });

    const editedTree = renderDialog();
    const editedMessageInput = findElement(editedTree, (element) => element.type === "textarea");
    const enabledSaveButton = findElement(
      editedTree,
      (element) =>
        typeof element.props.onClick === "function" &&
        ["Commit", "Save", "Committing...", "Saving..."].includes(textContent(element)),
    );

    expect(editedMessageInput?.props.value).toBe("  Save workflow to main  ");
    expect(enabledSaveButton?.props.disabled).toBe(false);

    enabledSaveButton?.props.onClick?.();

    const [variables, options] = mocks.workflowCommitMutate.mock.calls[0] ?? [];

    expect(mocks.genericCommitMutate).not.toHaveBeenCalled();
    expect(variables).toEqual({
      workflowId: "wf_1",
      payload: {
        yaml: "workflow:\n  name: Draft Flow\n",
        canvas_state: { nodes: [{ id: "node-1" }], edges: [] },
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

    const markup = renderToStaticMarkup(
      React.createElement(CommitDialog as unknown as React.ComponentType<Record<string, unknown>>, {
        open: true,
        onOpenChange: vi.fn(),
        onCommitSuccess: vi.fn(),
        files: [{ path: "custom/workflows/wf_1.yaml", status: "A" }],
        workflowId: "wf_1",
        draft: {
          yaml: "workflow:\n  name: Draft Flow\n",
          canvas_state: { nodes: [{ id: "node-1" }], edges: [] },
        },
      }),
    );

    expect(markup).toContain("workflow:\n  name: Draft Flow\n");
  });

  it("prevents duplicate submit while the workflow commit is pending", () => {
    mocks.workflowCommitPending = true;

    const pendingTree = renderDialog();

    const saveButton = findElement(
      pendingTree,
      (element) =>
        typeof element.props.onClick === "function" &&
        ["Commit", "Save", "Committing...", "Saving..."].includes(textContent(element)),
    );

    expect(saveButton?.props.disabled).toBe(true);
    expect(textContent(saveButton)).toMatch(/saving|committing/i);
  });
});
