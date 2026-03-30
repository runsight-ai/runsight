import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  stateValues: [] as unknown[],
  stateCursor: 0,
  updateWorkflowMutate: vi.fn(),
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
    useEffect: () => undefined,
    useCallback: <T extends (...args: never[]) => unknown>(fn: T) => fn,
    useRef: <T,>(initial: T) => ({ current: initial }),
  };
});

vi.mock("@/queries/workflows", () => ({
  useWorkflow: () => ({ data: { name: "Example Workflow" } }),
  useUpdateWorkflow: () => ({ mutate: mocks.updateWorkflowMutate }),
}));

vi.mock("@/queries/runs", () => ({
  useRun: () => ({ data: undefined }),
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

vi.mock("lucide-react", () => ({
  Save: () => React.createElement("span", null, "save"),
}));

const { CanvasTopbar } = await import("../CanvasTopbar");

function renderTopbar() {
  mocks.stateCursor = 0;

  return CanvasTopbar({
    workflowId: "wf_1",
    activeTab: "yaml",
    onValueChange: vi.fn(),
    isDirty: true,
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
  mocks.updateWorkflowMutate.mockReset();
});

describe("CanvasTopbar inline rename save contract (RUN-424)", () => {
  it("keeps a blurred inline name edit local until the explicit Save action", () => {
    const initialTree = renderTopbar();
    const workflowName = findElement(
      initialTree,
      (element) => element.type === "span" && textContent(element.props.children) === "Example Workflow",
    );

    expect(workflowName).toBeDefined();
    workflowName?.props.onClick?.();

    const editingTree = renderTopbar();
    const nameInput = findElement(editingTree, (element) => element.type === "input");

    expect(nameInput).toBeDefined();
    nameInput?.props.onChange?.({ target: { value: "Renamed Workflow" } });

    const dirtyTree = renderTopbar();
    const editedInput = findElement(dirtyTree, (element) => element.type === "input");

    expect(editedInput?.props.value).toBe("Renamed Workflow");

    editedInput?.props.onBlur?.();

    expect(mocks.updateWorkflowMutate).not.toHaveBeenCalled();
  });

  it("keeps the Enter key path local until the explicit Save action", () => {
    const initialTree = renderTopbar();
    const workflowName = findElement(
      initialTree,
      (element) => element.type === "span" && textContent(element.props.children) === "Example Workflow",
    );

    expect(workflowName).toBeDefined();
    workflowName?.props.onClick?.();

    const editingTree = renderTopbar();
    const nameInput = findElement(editingTree, (element) => element.type === "input");

    expect(nameInput).toBeDefined();
    nameInput?.props.onChange?.({ target: { value: "Renamed Workflow" } });

    const dirtyTree = renderTopbar();
    const editedInput = findElement(dirtyTree, (element) => element.type === "input");

    expect(editedInput?.props.value).toBe("Renamed Workflow");

    editedInput?.props.onKeyDown?.({ key: "Enter" });

    expect(mocks.updateWorkflowMutate).not.toHaveBeenCalled();
  });
});
