import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

type WorkflowUsage = {
  workflow_id: string;
  workflow_name: string;
};

type SoulLike = {
  id: string;
  role: string;
  provider: string;
  model_name: string;
  system_prompt: string;
  tools: string[];
  temperature: number;
  max_tool_iterations: number;
  avatar_color: string;
};

const mocks = vi.hoisted(() => {
  const deleteMutate = vi.fn(
    (
      variables: unknown,
      options?: {
        onSuccess?: () => void;
        onError?: (error: Error) => void;
      },
    ) => {
      mocks.deleteCalls.push({ variables, options });

      if (mocks.deleteOutcome === "success") {
        mocks.deleteError = undefined;
        options?.onSuccess?.();
        return;
      }

      const error = new Error("Delete failed");
      mocks.deleteError = error;
      options?.onError?.(error);
    },
  );

  return {
    stateValues: [] as unknown[],
    stateCursor: 0,
    dialogOpenChange: undefined as undefined | ((open: boolean) => void),
    onClose: vi.fn(),
    useSoulUsages: vi.fn(),
    usageState: {
      data: undefined as
        | undefined
        | {
            soul_id: string;
            usages: WorkflowUsage[];
            total: number;
          },
      isLoading: false,
      isError: false,
      error: undefined as Error | undefined,
    },
    deleteCalls: [] as Array<{
      variables: unknown;
      options?: {
        onSuccess?: () => void;
        onError?: (error: Error) => void;
      };
    }>,
    deleteOutcome: "success" as "success" | "error",
    deleteError: undefined as Error | undefined,
    deleteMutate,
    useDeleteSoul: vi.fn(),
  };
});

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
    useCallback: <T extends (...args: never[]) => unknown>(callback: T) => callback,
    useMemo: <T>(factory: () => T) => factory(),
    useRef: <T>(initialValue: T) => ({ current: initialValue }),
    useEffect: () => undefined,
    useLayoutEffect: () => undefined,
    useId: () => "mock-id",
  };
});

vi.mock("@base-ui/react/dialog", () => ({
  Dialog: {
    Root: ({
      open,
      onOpenChange,
      children,
      ...props
    }: {
      open?: boolean;
      onOpenChange?: (open: boolean) => void;
      children?: React.ReactNode;
    }) => {
      mocks.dialogOpenChange = onOpenChange;
      return React.createElement("dialog-root", { "data-open": String(Boolean(open)), ...props }, children);
    },
    Trigger: ({ children, ...props }: { children?: React.ReactNode }) =>
      React.createElement("dialog-trigger", props, children),
    Portal: ({ children }: { children?: React.ReactNode }) => React.createElement(React.Fragment, null, children),
    Close: ({
      render,
      children,
      ...props
    }: {
      render?: React.ReactElement;
      children?: React.ReactNode;
    }) => {
      const onClick = () => {
        mocks.dialogOpenChange?.(false);
      };

      if (React.isValidElement(render)) {
        return React.cloneElement(render, {
          ...render.props,
          ...props,
          onClick,
        }, children);
      }

      return React.createElement("button", { type: "button", ...props, onClick }, children);
    },
    Backdrop: ({ children, ...props }: { children?: React.ReactNode }) =>
      React.createElement("dialog-backdrop", props, children),
    Popup: ({ children, ...props }: { children?: React.ReactNode }) =>
      React.createElement("dialog-popup", props, children),
    Title: ({ children, ...props }: { children?: React.ReactNode }) =>
      React.createElement("h2", props, children),
    Description: ({ children, ...props }: { children?: React.ReactNode }) =>
      React.createElement("p", props, children),
  },
}));

vi.mock("@base-ui/react/button", () => ({
  Button: ({ children, ...props }: { children?: React.ReactNode }) =>
    React.createElement("button", { type: "button", ...props }, children),
}));

vi.mock("@runsight/ui/badge", () => ({
  Badge: ({ children, ...props }: { children?: React.ReactNode }) =>
    React.createElement("span", props, children),
}));

vi.mock("lucide-react", () => ({
  AlertTriangle: (props: Record<string, unknown>) =>
    React.createElement("svg", { ...props, "data-icon": "AlertTriangle" }),
  Loader2: (props: Record<string, unknown>) =>
    React.createElement("svg", { ...props, "data-icon": "Loader2" }),
  Trash2: (props: Record<string, unknown>) =>
    React.createElement("svg", { ...props, "data-icon": "Trash2" }),
  XIcon: (props: Record<string, unknown>) =>
    React.createElement("svg", { ...props, "data-icon": "XIcon" }),
  X: (props: Record<string, unknown>) => React.createElement("svg", { ...props, "data-icon": "X" }),
}));

vi.mock("@/queries/souls", () => ({
  useSoulUsages: (id: string | undefined) => {
    mocks.useSoulUsages(id);
    return mocks.usageState;
  },
  useDeleteSoul: () => {
    mocks.useDeleteSoul();
    return {
      mutate: mocks.deleteMutate,
      mutateAsync: async (variables: unknown) => {
        mocks.deleteMutate(variables, undefined);
      },
      isPending: false,
      error: mocks.deleteError,
    };
  },
}));

function makeSoul(overrides: Partial<SoulLike> = {}): SoulLike {
  return {
    id: "soul_123",
    role: "Researcher",
    provider: "openai",
    model_name: "gpt-4o",
    system_prompt: "You are a careful research assistant.",
    tools: ["browser"],
    temperature: 0.7,
    max_tool_iterations: 5,
    avatar_color: "accent",
    ...overrides,
  };
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

function findButton(
  node: React.ReactNode,
  label: string | RegExp,
): React.ReactElement | undefined {
  const matcher =
    typeof label === "string"
      ? (value: string) => value === label
      : (value: string) => label.test(value);

  return findElement(
    node,
    (element) => element.type === "button" && matcher(textContent(element)),
  );
}

async function renderDialog(overrides: Record<string, unknown> = {}) {
  mocks.stateCursor = 0;
  const { SoulDeleteDialog } = await import("../SoulDeleteDialog");

  return (
    SoulDeleteDialog as unknown as (props: Record<string, unknown>) => React.ReactElement | null
  )({
    open: true,
    onClose: mocks.onClose,
    soul: makeSoul(),
    ...overrides,
  });
}

function setUsageState({
  isLoading = false,
  isError = false,
  error,
  usages,
}: {
  isLoading?: boolean;
  isError?: boolean;
  error?: Error;
  usages?: WorkflowUsage[];
}) {
  mocks.usageState = {
    data:
      usages === undefined
        ? undefined
        : {
            soul_id: "soul_123",
            usages,
            total: usages.length,
          },
    isLoading,
    isError,
    error,
  };
}

beforeEach(() => {
  mocks.stateValues.length = 0;
  mocks.stateCursor = 0;
  mocks.dialogOpenChange = undefined;
  mocks.onClose.mockReset();
  mocks.useSoulUsages.mockReset();
  mocks.useDeleteSoul.mockReset();
  mocks.deleteCalls.length = 0;
  mocks.deleteOutcome = "success";
  mocks.deleteError = undefined;
  mocks.deleteMutate.mockClear();
  setUsageState({ usages: [] });
});

describe("SoulDeleteDialog behavior (RUN-451)", () => {
  it("does not request usages when the dialog is closed", async () => {
    await renderDialog({ open: false });

    expect(mocks.useSoulUsages).toHaveBeenCalledWith(undefined);
  });

  it("does not request usages when the soul is missing", async () => {
    await renderDialog({ soul: null });

    expect(mocks.useSoulUsages).toHaveBeenCalledWith(undefined);
  });

  it("requests usages for the active soul id when open", async () => {
    await renderDialog({ open: true, soul: makeSoul({ id: "soul_456" }) });

    expect(mocks.useSoulUsages).toHaveBeenCalledWith("soul_456");
  });

  it("shows a loading state that disables delete while usages are loading", async () => {
    setUsageState({ isLoading: true });

    const tree = await renderDialog();
    const deleteButton = findButton(tree, /Delete/);

    expect(textContent(tree)).toContain("Checking workflow usage");
    expect(deleteButton?.props.disabled).toBe(true);
  });

  it("renders a simple confirmation when the soul has no usages", async () => {
    setUsageState({ usages: [] });

    const tree = await renderDialog();
    const deleteButton = findButton(tree, "Delete");

    expect(textContent(tree)).toContain("Are you sure you want to delete");
    expect(textContent(tree)).toContain("Researcher");
    expect(textContent(tree)).not.toContain("Delete anyway");
    expect(deleteButton?.props.disabled).toBe(false);
  });

  it("renders three workflow names and a Delete anyway action when the soul has three usages", async () => {
    setUsageState({
      usages: [
        { workflow_id: "wf_1", workflow_name: "Research Flow" },
        { workflow_id: "wf_2", workflow_name: "Review Flow" },
        { workflow_id: "wf_3", workflow_name: "Deploy Flow" },
      ],
    });

    const tree = await renderDialog();
    const deleteButton = findButton(tree, /Delete anyway/);

    expect(textContent(tree)).toContain("Research Flow");
    expect(textContent(tree)).toContain("Review Flow");
    expect(textContent(tree)).toContain("Deploy Flow");
    expect(textContent(tree)).toContain("3 workflows");
    expect(deleteButton?.props.disabled).toBe(false);
  });

  it("caps the usage list at five workflow names and shows a +2 more indicator", async () => {
    setUsageState({
      usages: [
        { workflow_id: "wf_1", workflow_name: "Workflow 1" },
        { workflow_id: "wf_2", workflow_name: "Workflow 2" },
        { workflow_id: "wf_3", workflow_name: "Workflow 3" },
        { workflow_id: "wf_4", workflow_name: "Workflow 4" },
        { workflow_id: "wf_5", workflow_name: "Workflow 5" },
        { workflow_id: "wf_6", workflow_name: "Workflow 6" },
        { workflow_id: "wf_7", workflow_name: "Workflow 7" },
      ],
    });

    const tree = await renderDialog();

    expect(textContent(tree)).toContain("Workflow 1");
    expect(textContent(tree)).toContain("Workflow 2");
    expect(textContent(tree)).toContain("Workflow 3");
    expect(textContent(tree)).toContain("Workflow 4");
    expect(textContent(tree)).toContain("Workflow 5");
    expect(textContent(tree)).toContain("+2 more");
    expect(textContent(tree)).not.toContain("Workflow 6");
    expect(textContent(tree)).not.toContain("Workflow 7");
  });

  it("shows a caution warning and keeps delete enabled when usage lookup fails", async () => {
    setUsageState({
      isError: true,
      error: new Error("Network down"),
    });

    const tree = await renderDialog();
    const deleteButton = findButton(tree, /Delete/);

    expect(textContent(tree)).toContain("Could not check workflow usage");
    expect(deleteButton?.props.disabled).toBe(false);
  });

  it("closes without deleting when the dialog X is clicked", async () => {
    setUsageState({ usages: [] });

    const tree = await renderDialog();
    const closeButton = findButton(tree, "Close");

    closeButton?.props.onClick?.();

    expect(mocks.onClose).toHaveBeenCalledTimes(1);
    expect(mocks.deleteMutate).not.toHaveBeenCalled();
  });

  it("closes without deleting when the dialog requests Escape close", async () => {
    setUsageState({ usages: [] });

    await renderDialog();
    mocks.dialogOpenChange?.(false);

    expect(mocks.onClose).toHaveBeenCalledTimes(1);
    expect(mocks.deleteMutate).not.toHaveBeenCalled();
  });

  it("uses force-delete plumbing and closes on a successful confirm", async () => {
    setUsageState({
      usages: [
        { workflow_id: "wf_1", workflow_name: "Research Flow" },
        { workflow_id: "wf_2", workflow_name: "Review Flow" },
        { workflow_id: "wf_3", workflow_name: "Deploy Flow" },
      ],
    });
    mocks.deleteOutcome = "success";

    const tree = await renderDialog();
    const confirmButton = findButton(tree, "Delete anyway");

    confirmButton?.props.onClick?.();

    expect(mocks.deleteMutate).toHaveBeenCalledWith(
      { id: "soul_123", force: true },
      expect.objectContaining({
        onSuccess: expect.any(Function),
        onError: expect.any(Function),
      }),
    );
    expect(mocks.onClose).toHaveBeenCalledTimes(1);
  });

  it("surfaces delete failures to the user after confirm", async () => {
    setUsageState({
      usages: [
        { workflow_id: "wf_1", workflow_name: "Research Flow" },
        { workflow_id: "wf_2", workflow_name: "Review Flow" },
        { workflow_id: "wf_3", workflow_name: "Deploy Flow" },
      ],
    });
    mocks.deleteOutcome = "error";

    let tree = await renderDialog();
    const confirmButton = findButton(tree, "Delete anyway");

    confirmButton?.props.onClick?.();
    tree = await renderDialog();

    expect(textContent(tree)).toContain("Delete failed");
    expect(mocks.onClose).not.toHaveBeenCalled();
  });
});
