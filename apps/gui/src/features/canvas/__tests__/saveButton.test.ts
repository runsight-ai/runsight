import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  buttonProps: [] as Array<Record<string, unknown>>,
  updateWorkflowMutate: vi.fn(),
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
}));

vi.mock("react", async () => {
  const actual = await vi.importActual<typeof React>("react");

  return {
    ...actual,
    useEffect: (effect: () => void | (() => void)) => {
      effect();
    },
  };
});

vi.mock("@runsight/ui/button", () => ({
  Button: (props: Record<string, unknown>) => {
    mocks.buttonProps.push(props);
    return React.createElement("button", { type: "button" }, props.children);
  },
}));

vi.mock("@runsight/ui/tabs", () => ({
  Tabs: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", null, children),
  TabsList: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", null, children),
  TabsTrigger: ({ children }: { children: React.ReactNode }) =>
    React.createElement("button", { type: "button" }, children),
}));

vi.mock("../RunButton", () => ({
  RunButton: () => React.createElement("div", null, "Run"),
}));

vi.mock("../ExecutionMetrics", () => ({
  ExecutionMetrics: () => React.createElement("div", null, "Execution Metrics"),
}));

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

vi.mock("lucide-react", () => ({
  Save: () => React.createElement("span", null, "save"),
}));

const { CanvasTopbar } = await import("../CanvasTopbar");

function findSaveButton() {
  const saveButton = mocks.buttonProps.find((props) =>
    React.Children.toArray(props.children).some((child) => child === "Save"),
  );

  expect(saveButton).toBeDefined();
  return saveButton as { onClick?: () => void; variant?: string };
}

function renderTopbar(overrides: Partial<React.ComponentProps<typeof CanvasTopbar>> = {}) {
  mocks.buttonProps.length = 0;

  const markup = renderToStaticMarkup(
    React.createElement(CanvasTopbar, {
      workflowId: "wf_1",
      activeTab: "yaml",
      onValueChange: vi.fn(),
      ...overrides,
    }),
  );

  return { markup, saveButton: findSaveButton() };
}

beforeEach(() => {
  mocks.buttonProps.length = 0;
  mocks.updateWorkflowMutate.mockReset();
  mocks.addEventListener.mockReset();
  mocks.removeEventListener.mockReset();

  vi.stubGlobal("window", {
    addEventListener: mocks.addEventListener,
    removeEventListener: mocks.removeEventListener,
  });
});

describe("CanvasTopbar save behavior (RUN-433)", () => {
  it("renders a quiet save button when the canvas is clean", () => {
    const { markup, saveButton } = renderTopbar({ isDirty: false });

    expect(saveButton.variant).toBe("ghost");
    expect(markup).not.toContain('aria-label="unsaved indicator"');
  });

  it("shows a dirty cue and emphasizes save when the canvas has unsaved changes", () => {
    const { markup, saveButton } = renderTopbar({ isDirty: true });

    expect(saveButton.variant).toBe("primary");
    expect(markup).toContain('aria-label="unsaved indicator"');
  });

  it("routes the save button through the explicit onSave path", () => {
    const onSave = vi.fn();
    const { saveButton } = renderTopbar({ isDirty: true, onSave });

    saveButton.onClick?.();

    expect(onSave).toHaveBeenCalledTimes(1);
  });

  it("routes Cmd+S through the same explicit onSave path", () => {
    const onSave = vi.fn();

    renderTopbar({ onSave });

    const keydownHandler = mocks.addEventListener.mock.calls.find(
      ([eventName]) => eventName === "keydown",
    )?.[1] as ((event: KeyboardEvent) => void) | undefined;

    expect(keydownHandler).toBeTypeOf("function");

    const event = {
      metaKey: true,
      ctrlKey: false,
      key: "s",
      preventDefault: vi.fn(),
    } as unknown as KeyboardEvent;

    keydownHandler?.(event);

    expect(event.preventDefault).toHaveBeenCalledTimes(1);
    expect(onSave).toHaveBeenCalledTimes(1);
  });
});
