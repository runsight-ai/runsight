import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
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
  const queryState = {
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
  };

  const deleteState = {
    outcome: "success" as "success" | "error",
    error: undefined as Error | undefined,
  };

  const api = {
    getSoulUsages: vi.fn(),
    deleteSoul: vi.fn(),
  };

  return {
    stateValues: [] as unknown[],
    stateCursor: 0,
    dialogOpenChange: undefined as undefined | ((open: boolean) => void),
    onClose: vi.fn(),
    useSoulUsages: vi.fn((id: string | undefined) => {
      mocks.queryCalls.push({ id });
      return mocks.queryState;
    }),
    useDeleteSoul: vi.fn(() => ({
      mutate: (
        variables: unknown,
        callbacks?: {
          onSuccess?: (data: unknown, variables: unknown, context: unknown) => void;
          onError?: (error: Error, variables: unknown, context: unknown) => void;
        },
      ) => {
        mocks.mutateCalls.push({ variables, callbacks });

        if (mocks.deleteState.outcome === "success") {
          const id = typeof variables === "string" ? variables : (variables as { id?: string }).id;
          const result = mocks.api.deleteSoul(id);
          callbacks?.onSuccess?.(result, variables, undefined);
          return result;
        }

        const error = mocks.deleteState.error ?? new Error("Delete failed");
        callbacks?.onError?.(error, variables, undefined);
        return undefined;
      },
      isPending: false,
      error: mocks.deleteState.error,
    })),
    queryCalls: [] as Array<Record<string, unknown>>,
    mutationCalls: [] as Array<Record<string, unknown>>,
    mutateCalls: [] as Array<{
      variables: unknown;
      callbacks?: {
        onSuccess?: (data: unknown, variables: unknown, context: unknown) => void;
        onError?: (error: Error, variables: unknown, context: unknown) => void;
      };
    }>,
    queryState,
    deleteState,
    api,
    invalidateQueries: vi.fn(),
    toastSuccess: vi.fn(),
    toastError: vi.fn(),
    useQuery: vi.fn((options: Record<string, unknown>) => {
      mocks.queryCalls.push(options);
      return mocks.queryState;
    }),
    useMutation: vi.fn((options: Record<string, unknown>) => {
      mocks.mutationCalls.push(options);

      return {
        mutate: (
          variables: unknown,
          callbacks?: {
            onSuccess?: (data: unknown, variables: unknown, context: unknown) => void;
            onError?: (error: Error, variables: unknown, context: unknown) => void;
          },
        ) => {
          mocks.mutateCalls.push({ variables, callbacks });

          if (mocks.deleteState.outcome === "success") {
            const result = (options.mutationFn as (value: unknown) => unknown)(variables);
            (options.onSuccess as
              | undefined
              | ((data: unknown, variables: unknown, context: unknown) => void))?.(
              result,
              variables,
              undefined,
            );
            callbacks?.onSuccess?.(result, variables, undefined);
            return result;
          }

          const error = mocks.deleteState.error ?? new Error("Delete failed");
          (options.onError as
            | undefined
            | ((error: Error, variables: unknown, context: unknown) => void))?.(
            error,
            variables,
            undefined,
          );
          callbacks?.onError?.(error, variables, undefined);
          return undefined;
        },
        isPending: false,
        error: mocks.deleteState.error,
      };
    }),
    useQueryClient: vi.fn(() => ({
      invalidateQueries: mocks.invalidateQueries,
    })),
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

function createRunsightDialogModule() {
  return {
    Dialog: ({
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
    DialogContent: ({
      children,
      ...props
    }: {
      children?: React.ReactNode;
    }) => React.createElement("dialog-content", props, children),
    DialogHeader: ({
      children,
      ...props
    }: {
      children?: React.ReactNode;
    }) => React.createElement("dialog-header", props, children),
    DialogFooter: ({
      children,
      ...props
    }: {
      children?: React.ReactNode;
    }) => React.createElement("dialog-footer", props, children),
    DialogTitle: ({
      children,
      ...props
    }: {
      children?: React.ReactNode;
    }) => React.createElement("h2", props, children),
    DialogDescription: ({
      children,
      ...props
    }: {
      children?: React.ReactNode;
    }) => React.createElement("p", props, children),
    DialogBody: ({
      children,
      ...props
    }: {
      children?: React.ReactNode;
    }) => React.createElement("dialog-body", props, children),
    DialogOverlay: ({
      children,
      ...props
    }: {
      children?: React.ReactNode;
    }) => React.createElement("dialog-overlay", props, children),
    DialogPortal: ({ children }: { children?: React.ReactNode }) =>
      React.createElement(React.Fragment, null, children),
    DialogClose: ({
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
        return React.cloneElement(
          render,
          {
            ...render.props,
            ...props,
            onClick,
          },
          children,
        );
      }

      return React.createElement("button", { type: "button", ...props, onClick }, children);
    },
    DialogTrigger: ({
      children,
      ...props
    }: {
      children?: React.ReactNode;
    }) => React.createElement("button", props, children),
  };
}

const runsightDialog = createRunsightDialogModule();

vi.mock("@base-ui/react/dialog", () => ({
  Dialog: {
    Root: runsightDialog.Dialog,
    Trigger: runsightDialog.DialogTrigger,
    Portal: runsightDialog.DialogPortal,
    Close: runsightDialog.DialogClose,
    Backdrop: runsightDialog.DialogOverlay,
    Popup: runsightDialog.DialogContent,
    Title: runsightDialog.DialogTitle,
    Description: runsightDialog.DialogDescription,
  },
}));

vi.mock("@runsight/ui/dialog", () => runsightDialog);

vi.mock("@runsight/ui/button", () => ({
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
  X: (props: Record<string, unknown>) => React.createElement("svg", { ...props, "data-icon": "X" }),
  XIcon: (props: Record<string, unknown>) =>
    React.createElement("svg", { ...props, "data-icon": "XIcon" }),
}));

vi.mock("@/queries/souls", () => ({
  useSoulUsages: mocks.useSoulUsages,
  useDeleteSoul: mocks.useDeleteSoul,
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

function markup(node: React.ReactNode): string {
  return renderToStaticMarkup(React.createElement(React.Fragment, null, node));
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
  mocks.queryState.data =
    usages === undefined
      ? undefined
      : {
          soul_id: "soul_123",
          usages,
          total: usages.length,
        };
  mocks.queryState.isLoading = isLoading;
  mocks.queryState.isError = isError;
  mocks.queryState.error = error;
}

function setDeleteOutcome(outcome: "success" | "error", error?: Error) {
  mocks.deleteState.outcome = outcome;
  mocks.deleteState.error = error;
}

beforeEach(() => {
  mocks.stateValues.length = 0;
  mocks.stateCursor = 0;
  mocks.dialogOpenChange = undefined;
  mocks.onClose.mockReset();
  mocks.useSoulUsages.mockReset();
  mocks.useDeleteSoul.mockReset();
  mocks.queryCalls.length = 0;
  mocks.mutateCalls.length = 0;
  mocks.api.getSoulUsages.mockReset();
  mocks.api.deleteSoul.mockReset();
  mocks.invalidateQueries.mockReset();
  setUsageState({ usages: [] });
  setDeleteOutcome("success");
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
    const html = markup(tree);

    expect(html).toContain("Checking workflow usage");
    expect(deleteButton?.props.disabled).toBe(true);
  });

  it("renders a simple confirmation when the soul has no usages", async () => {
    setUsageState({ usages: [] });

    const tree = await renderDialog();
    const deleteButton = findButton(tree, "Delete");
    const html = markup(tree);

    expect(html).toContain("Are you sure you want to delete");
    expect(html).toContain("Researcher");
    expect(html).not.toContain("Delete anyway");
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
    const html = markup(tree);

    expect(html).toContain("Research Flow");
    expect(html).toContain("Review Flow");
    expect(html).toContain("Deploy Flow");
    expect(html).toContain("3 workflows");
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
    const html = markup(tree);

    expect(html).toContain("Workflow 1");
    expect(html).toContain("Workflow 2");
    expect(html).toContain("Workflow 3");
    expect(html).toContain("Workflow 4");
    expect(html).toContain("Workflow 5");
    expect(html).toContain("+2 more");
    expect(html).not.toContain("Workflow 6");
    expect(html).not.toContain("Workflow 7");
  });

  it("shows a caution warning and keeps delete enabled when usage lookup fails", async () => {
    setUsageState({
      isError: true,
      error: new Error("Network down"),
    });

    const tree = await renderDialog();
    const deleteButton = findButton(tree, /Delete/);
    const html = markup(tree);

    expect(html).toContain("Could not check workflow usage");
    expect(html).toContain("Network down");
    expect(deleteButton?.props.disabled).toBe(false);
  });

  it("closes without deleting when the dialog X is clicked", async () => {
    setUsageState({ usages: [] });

    const tree = await renderDialog();
    const closeButton = findButton(tree, "Close");

    closeButton?.props.onClick?.();

    expect(mocks.onClose).toHaveBeenCalledTimes(1);
    expect(mocks.api.deleteSoul).not.toHaveBeenCalled();
  });

  it("closes without deleting when the dialog requests Escape close", async () => {
    setUsageState({ usages: [] });

    await renderDialog();
    mocks.dialogOpenChange?.(false);

    expect(mocks.onClose).toHaveBeenCalledTimes(1);
    expect(mocks.api.deleteSoul).not.toHaveBeenCalled();
  });

  it("uses force-delete plumbing and closes on a successful confirm", async () => {
    setUsageState({
      usages: [
        { workflow_id: "wf_1", workflow_name: "Research Flow" },
        { workflow_id: "wf_2", workflow_name: "Review Flow" },
        { workflow_id: "wf_3", workflow_name: "Deploy Flow" },
      ],
    });
    setDeleteOutcome("success");

    const tree = await renderDialog();
    const confirmButton = findButton(tree, "Delete anyway");

    confirmButton?.props.onClick?.();

    expect(mocks.mutateCalls[0]?.variables).toEqual({
      id: "soul_123",
      force: true,
    });
    expect(mocks.api.deleteSoul).toHaveBeenCalledWith("soul_123", true);
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
    setDeleteOutcome("error", new Error("Delete failed"));

    let tree = await renderDialog();
    const confirmButton = findButton(tree, "Delete anyway");

    confirmButton?.props.onClick?.();
    tree = await renderDialog();
    const html = markup(tree);

    expect(html).toContain("Delete failed");
    expect(mocks.onClose).not.toHaveBeenCalled();
  });
});
