import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

export const defaultWorkflowCommitFiles = [
  { path: "custom/workflows/review_flow.yaml", status: "A" },
];

export const defaultWorkflowDraft = {
  yaml: "workflow:\n  name: Draft Flow\n",
  canvas_state: { nodes: [{ id: "draft-soul-node" }], edges: [] },
};

export const defaultGitDiff = {
  diff: "diff --git a/custom/workflows/review_flow.yaml b/custom/workflows/review_flow.yaml",
};

type CommitDialogComponent = (props: Record<string, unknown>) => React.ReactElement | null;

type StatefulCommitMocks = {
  stateCursor: number;
};

export function renderCommitDialogTree(
  CommitDialog: unknown,
  mocks: StatefulCommitMocks,
  overrides: Record<string, unknown> = {},
) {
  mocks.stateCursor = 0;

  return (CommitDialog as CommitDialogComponent)({
    open: true,
    onOpenChange: () => undefined,
    onCommitSuccess: () => undefined,
    files: defaultWorkflowCommitFiles,
    workflowId: "review_flow",
    draft: defaultWorkflowDraft,
    ...overrides,
  });
}

export function renderCommitDialogMarkup(
  CommitDialog: unknown,
  overrides: Record<string, unknown> = {},
) {
  return renderToStaticMarkup(
    React.createElement(CommitDialog as React.ComponentType<Record<string, unknown>>, {
      open: true,
      onOpenChange: () => undefined,
      onCommitSuccess: () => undefined,
      files: defaultWorkflowCommitFiles,
      workflowId: "review_flow",
      draft: defaultWorkflowDraft,
      ...overrides,
    }),
  );
}

export function textContent(node: React.ReactNode): string {
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

export function findElement(
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

export function findCommitSaveButton(node: React.ReactNode) {
  return findElement(
    node,
    (element) =>
      typeof element.props.onClick === "function" &&
      ["Commit", "Save", "Committing...", "Saving..."].includes(textContent(element)),
  );
}
