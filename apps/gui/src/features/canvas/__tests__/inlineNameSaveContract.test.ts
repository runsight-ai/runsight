import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  stateValues: [] as unknown[],
  stateCursor: 0,
}));

vi.mock("react", async () => {
  const actual = await vi.importActual<typeof React>("react");

  return {
    ...actual,
    useContext: actual.useContext,
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
    useEffect: () => undefined,
    useCallback: <T extends (...args: never[]) => unknown>(fn: T) => fn,
    useRef: <T,>(initial: T) => ({ current: initial }),
  };
});

vi.mock("@/queries/workflows", () => ({
  useWorkflow: () => ({ data: { name: "Example Workflow" } }),
  useUpdateWorkflow: () => ({ mutate: vi.fn() }),
}));

vi.mock("@/queries/runs", () => ({
  useRun: () => ({ data: undefined }),
  useCancelRun: () => ({ mutate: vi.fn() }),
}));

vi.mock("@/store/canvas", () => ({
  useCanvasStore: (selector: (store: { activeRunId: string | null }) => unknown) =>
    selector({ activeRunId: null }),
}));

vi.mock("@runsight/ui/tabs", () => ({
  Tabs: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", null, children),
  TabsList: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", null, children),
  TabsTrigger: ({ children }: { children: React.ReactNode }) =>
    React.createElement("button", { type: "button" }, children),
}));

vi.mock("@runsight/ui/button", () => ({
  Button: (props: Record<string, unknown>) =>
    React.createElement("button", { type: "button", ...props }, props.children),
}));

vi.mock("../RunButton", () => ({
  RunButton: () => React.createElement("div", null, "Run"),
}));

vi.mock("../ExecutionMetrics", () => ({
  ExecutionMetrics: () => React.createElement("div", null, "Execution Metrics"),
}));

vi.mock("react-router", () => ({
  useInRouterContext: () => false,
  Link: (props: Record<string, unknown>) => React.createElement("a", props, props.children),
}));

vi.mock("../useForkWorkflow", () => ({
  useForkWorkflow: () => ({ forkWorkflow: vi.fn(), isForking: false }),
}));

vi.mock("@runsight/ui/badge", () => ({
  Badge: (props: Record<string, unknown>) => React.createElement("span", props, props.children),
}));

vi.mock("@/components/shared", () => ({
  WorkflowTopbar: (props: Record<string, unknown>) =>
    React.createElement("div", null, props.title as React.ReactNode, props.actions as React.ReactNode, props.children as React.ReactNode),
}));

vi.mock("lucide-react", () => ({
  Save: () => React.createElement("span", null, "save"),
  X: () => React.createElement("span", null, "x"),
}));

const { CanvasTopbar } = await import("../CanvasTopbar");

function renderTopbar(onSave = vi.fn()) {
  mocks.stateCursor = 0;

  const tree = CanvasTopbar({
    workflowId: "wf_1",
    activeTab: "yaml",
    onValueChange: vi.fn(),
    isDirty: true,
    onSave,
  });

  // The component returns a <WorkflowTopbar> element whose type is the mock function.
  // Resolve it by calling the mock to get the actual React tree.
  if (React.isValidElement(tree) && typeof tree.type === "function") {
    return (tree.type as (props: Record<string, unknown>) => React.ReactNode)(tree.props as Record<string, unknown>);
  }
  return tree;
}

function _textContent(node: React.ReactNode): string {
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
});

describe("CanvasTopbar inline rename save contract (RUN-424)", () => {
  it("does not trigger the explicit production save path when a blurred inline rename completes", () => {
    const onSave = vi.fn();
    const initialTree = renderTopbar(onSave);
    const workflowName = findElement(
      initialTree,
      (element) => element.props?.["data-testid"] === "workflow-name-display",
    );

    expect(workflowName).toBeDefined();
    workflowName?.props.onClick?.();

    const editingTree = renderTopbar();
    const nameInput = findElement(editingTree, (element) => element.props?.["data-testid"] === "workflow-name-input" || element.type === "input");

    expect(nameInput).toBeDefined();
    nameInput?.props.onChange?.({ target: { value: "Renamed Workflow" } });

    const dirtyTree = renderTopbar();
    const editedInput = findElement(dirtyTree, (element) => element.props?.["data-testid"] === "workflow-name-input" || element.type === "input");

    expect(editedInput?.props.value).toBe("Renamed Workflow");

    editedInput?.props.onBlur?.();

    expect(onSave).not.toHaveBeenCalled();
  });

  it("does not trigger the explicit production save path when inline rename is confirmed with Enter", () => {
    const onSave = vi.fn();
    const initialTree = renderTopbar(onSave);
    const workflowName = findElement(
      initialTree,
      (element) => element.props?.["data-testid"] === "workflow-name-display",
    );

    expect(workflowName).toBeDefined();
    workflowName?.props.onClick?.();

    const editingTree = renderTopbar();
    const nameInput = findElement(editingTree, (element) => element.props?.["data-testid"] === "workflow-name-input" || element.type === "input");

    expect(nameInput).toBeDefined();
    nameInput?.props.onChange?.({ target: { value: "Renamed Workflow" } });

    const dirtyTree = renderTopbar();
    const editedInput = findElement(dirtyTree, (element) => element.props?.["data-testid"] === "workflow-name-input" || element.type === "input");

    expect(editedInput?.props.value).toBe("Renamed Workflow");

    editedInput?.props.onKeyDown?.({ key: "Enter" });

    expect(onSave).not.toHaveBeenCalled();
  });
});
