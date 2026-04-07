import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import type * as ReactJsxRuntime from "react/jsx-runtime";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  workflows: [
    {
      id: "wf_research",
      name: "Research & Review",
      description: "Customer interviews and synthesis",
      block_count: 3,
      modified_at: Date.parse("2026-03-31T10:00:00Z") / 1000,
      commit_sha: "f078f13deadbeef",
      health: {
        run_count: 12,
        eval_pass_pct: 92,
        eval_health: "success",
        total_cost_usd: 0.42,
        regression_count: 0,
      },
    },
    {
      id: "wf_pipeline",
      name: "Content Pipeline",
      description: "Documentation search index refresh",
      block_count: 5,
      modified_at: Date.parse("2026-03-31T08:00:00Z") / 1000,
      commit_sha: null,
      health: {
        run_count: 0,
        eval_pass_pct: null,
        eval_health: null,
        total_cost_usd: 0,
        regression_count: 0,
      },
    },
    {
      id: "wf_docs",
      name: "Daily Digest",
      description: "Schema docs review queue",
      block_count: 2,
      modified_at: Date.parse("2026-03-30T10:00:00Z") / 1000,
      commit_sha: "a46326399999999",
      health: {
        run_count: 8,
        eval_pass_pct: 75,
        eval_health: "warning",
        total_cost_usd: 0.24,
        regression_count: 1,
      },
    },
  ],
  stateValues: [] as unknown[],
  stateCursor: 0,
  navigate: vi.fn(),
  searchParams: new URLSearchParams(),
  setSearchParams: vi.fn(),
  refetch: vi.fn(),
  createWorkflow: vi.fn(),
  createWorkflowAsync: vi.fn(),
  deleteWorkflow: vi.fn(),
  setWorkflowEnabled: vi.fn(),
  queryState: {
    data: {
      items: [] as Array<Record<string, unknown>>,
      total: 0,
    },
    isLoading: false,
    error: null as Error | null,
  },
  deletePending: false,
  createPending: false,
  inputProps: [] as Array<Record<string, unknown>>,
  buttonProps: [] as Array<Record<string, unknown>>,
  rowProps: [] as Array<Record<string, unknown>>,
  emptyStateActions: [] as Array<{ label: string; onClick?: () => void }>,
  skeletonProps: [] as Array<Record<string, unknown>>,
  rowActions: [] as Array<{ workflow: { id: string; name?: string | null }; deleteRow?: () => void }>,
  tabTriggers: [] as Array<{ value: string; disabled: boolean; active: boolean; onClick?: () => void }>,
  deleteDialogs: [] as Array<Record<string, unknown>>,
  jsxElements: [] as Array<{ type: unknown; props: Record<string, unknown> }>,
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

vi.mock("react/jsx-runtime", async () => {
  const actual = await vi.importActual<typeof ReactJsxRuntime>(
    "react/jsx-runtime",
  );

  function record(
    factory: typeof actual.jsx,
    type: Parameters<typeof actual.jsx>[0],
    props: Parameters<typeof actual.jsx>[1],
    key?: Parameters<typeof actual.jsx>[2],
  ) {
    if (typeof type === "string") {
      mocks.jsxElements.push({
        type,
        props: (props ?? {}) as Record<string, unknown>,
      });
    }

    return factory(type, props, key);
  }

  return {
    ...actual,
    jsx: (
      type: Parameters<typeof actual.jsx>[0],
      props: Parameters<typeof actual.jsx>[1],
      key?: Parameters<typeof actual.jsx>[2],
    ) => record(actual.jsx, type, props, key),
    jsxs: (
      type: Parameters<typeof actual.jsxs>[0],
      props: Parameters<typeof actual.jsxs>[1],
      key?: Parameters<typeof actual.jsxs>[2],
    ) => record(actual.jsxs, type, props, key),
  };
});

vi.mock("react-router", () => ({
  useNavigate: () => mocks.navigate,
  useSearchParams: () => [
    mocks.searchParams,
    (next: string | URLSearchParams | Record<string, string>) => {
      const params =
        typeof next === "string"
          ? new URLSearchParams(next)
          : next instanceof URLSearchParams
            ? new URLSearchParams(next)
            : new URLSearchParams(Object.entries(next));

      mocks.searchParams = params;
      mocks.setSearchParams(params);
    },
  ],
}));

vi.mock("@/queries/workflows", () => ({
  useWorkflows: () => ({
    data: mocks.queryState.data,
    isLoading: mocks.queryState.isLoading,
    error: mocks.queryState.error,
    refetch: mocks.refetch,
  }),
  useCreateWorkflow: () => ({
    mutate: mocks.createWorkflow,
    mutateAsync: mocks.createWorkflowAsync,
    isPending: mocks.createPending,
  }),
  useDeleteWorkflow: () => ({
    mutateAsync: mocks.deleteWorkflow,
    isPending: mocks.deletePending,
  }),
  useSetWorkflowEnabled: () => ({
    mutateAsync: mocks.setWorkflowEnabled,
    isPending: false,
  }),
  useWorkflowRegressions: () => ({
    data: undefined,
  }),
}));

vi.mock("@/components/shared/PageHeader", () => ({
  PageHeader: ({
    title,
    actions,
  }: {
    title: string;
    actions?: React.ReactNode;
  }) => React.createElement("header", null, [
    React.createElement("h1", { key: "title" }, title),
    React.createElement("div", { key: "actions" }, actions),
  ]),
}));

vi.mock("@/components/shared", () => ({
  PageHeader: ({
    title,
    actions,
  }: {
    title: string;
    actions?: React.ReactNode;
  }) => React.createElement("header", null, [
    React.createElement("h1", { key: "title" }, title),
    React.createElement("div", { key: "actions" }, actions),
  ]),
}));

vi.mock("@/components/shared/DeleteConfirmDialog", () => ({
  DeleteConfirmDialog: (props: Record<string, unknown>) => {
    mocks.deleteDialogs.push(props);

    if (!props.open) {
      return null;
    }

    return React.createElement("section", { role: "dialog" }, [
      React.createElement("h2", { key: "title" }, `Delete ${props.resourceName ?? "Workflow"}`),
      React.createElement(
        "p",
        { key: "description" },
        `Delete "${String(props.itemName ?? "Untitled")}"? This action cannot be undone.`,
      ),
      React.createElement(
        "button",
        { key: "confirm", type: "button", onClick: props.onConfirm as (() => void) | undefined },
        "Delete",
      ),
    ]);
  },
}));

vi.mock("@runsight/ui/button", () => ({
  Button: (props: Record<string, unknown>) => {
    mocks.buttonProps.push(props);

    return React.createElement(
      "button",
      {
        type: "button",
        ...props,
      },
      props.children,
    );
  },
}));

vi.mock("@runsight/ui/input", () => ({
  Input: (props: Record<string, unknown>) => {
    mocks.inputProps.push(props);

    return React.createElement("input", {
      ...props,
      value: props.value ?? "",
    });
  },
}));

vi.mock("@runsight/ui/empty-state", () => ({
  EmptyState: ({
    title,
    description,
    action,
  }: {
    title: string;
    description?: string;
    action?: { label: string; onClick?: () => void };
  }) => {
    if (action) {
      mocks.emptyStateActions.push(action);
    }

    return React.createElement("section", null, [
      React.createElement("h2", { key: "title" }, title),
      description ? React.createElement("p", { key: "description" }, description) : null,
      action
        ? React.createElement(
            "button",
            {
              key: "action",
              type: "button",
              onClick: action.onClick,
            },
            action.label,
          )
        : null,
    ]);
  },
}));

vi.mock("@runsight/ui/skeleton", () => ({
  Skeleton: (props: Record<string, unknown>) => {
    mocks.skeletonProps.push(props);

    return React.createElement("div", {
      ...props,
      "data-testid": "shared-skeleton",
      "data-slot": "skeleton",
    });
  },
}));

vi.mock("@runsight/ui/tabs", () => {
  return {
    Tabs: ({
      value,
      defaultValue,
      _onValueChange,
      children,
    }: {
      value?: string;
      defaultValue?: string;
      _onValueChange?: (value: string) => void;
      children: React.ReactNode;
    }) => {
      const tabValue = value ?? defaultValue ?? "";

      mocks.tabTriggers.length = 0;

      return React.createElement("div", { "data-tab-value": tabValue }, children);
    },
    TabsList: ({ children, ...props }: Record<string, unknown>) =>
      React.createElement("div", props, children),
    TabsTrigger: ({
      value,
      disabled,
      children,
      ...props
    }: {
      value: string;
      disabled?: boolean;
      children: React.ReactNode;
    }) => {
      mocks.tabTriggers.push({
        value,
        disabled: Boolean(disabled),
        active: true,
        onClick: () => {},
      });

      return React.createElement(
        "button",
        {
          type: "button",
          role: "tab",
          "aria-selected": true,
          "aria-disabled": disabled ? "true" : "false",
          disabled,
          ...props,
        },
        children,
      );
    },
    TabsContent: ({
      value: _value,
      children,
      ...props
    }: {
      value: string;
      children: React.ReactNode;
    }) => {
      return React.createElement("section", props, children);
    },
  };
});

vi.mock("../WorkflowRow", () => ({
  WorkflowRow: (props: Record<string, unknown>) => {
    mocks.rowProps.push(props);

    const workflow = (props.workflow ??
      props.item) as { id: string; name?: string | null } | undefined;
    const deleteRow =
      (props.onDelete as ((workflow: { id: string; name?: string | null }) => void) | undefined) ??
      (props.onDeleteClick as
        | ((workflow: { id: string; name?: string | null }) => void)
        | undefined) ??
      (props.onRequestDelete as
        | ((workflow: { id: string; name?: string | null }) => void)
        | undefined);

    if (workflow) {
      mocks.rowActions.push({
        workflow,
        deleteRow: deleteRow ? () => deleteRow(workflow) : undefined,
      });
    }

    return React.createElement("div", null, [
      React.createElement("span", { key: "name" }, workflow?.name ?? "Untitled"),
      React.createElement(
        "button",
        {
          key: "delete",
          type: "button",
          "aria-label": `Delete ${workflow?.name ?? "Untitled"} workflow`,
          onClick: workflow && deleteRow ? () => deleteRow(workflow) : undefined,
        },
        "Delete",
      ),
    ]);
  },
  default: (props: Record<string, unknown>) =>
    React.createElement("div", null, JSON.stringify(props)),
}));

vi.mock("../RunsTab", () => ({
  RunsTab: ({ onGoToWorkflows }: { onGoToWorkflows?: () => void }) =>
    React.createElement("section", { "data-testid": "runs-tab-shell" }, [
      React.createElement("h2", { key: "title" }, "Runs tab shell"),
      React.createElement(
        "button",
        {
          key: "go-to-workflows",
          type: "button",
          onClick: onGoToWorkflows,
        },
        "Go to Workflows",
      ),
    ]),
}));

vi.mock("lucide-react", () => {
  const icon = (name: string) =>
    function Icon() {
      return React.createElement("svg", { "data-icon": name });
    };

  return new Proxy(
    {},
    {
      get: (_target, key) => icon(String(key)),
    },
  );
});

async function loadWorkflowsTabComponent() {
  const module = await import("../WorkflowsTab");
  return (module.Component ?? (module as Record<string, unknown>).WorkflowsTab) as React.ComponentType;
}

async function renderWorkflowsTab() {
  mocks.stateCursor = 0;
  mocks.inputProps.length = 0;
  mocks.buttonProps.length = 0;
  mocks.rowProps.length = 0;
  mocks.emptyStateActions.length = 0;
  mocks.skeletonProps.length = 0;
  mocks.rowActions.length = 0;
  mocks.deleteDialogs.length = 0;
  mocks.jsxElements.length = 0;

  const WorkflowsTab = await loadWorkflowsTabComponent();
  const html = renderToStaticMarkup(React.createElement(WorkflowsTab));

  return {
    html,
    input: mocks.inputProps.at(-1) as { onChange?: (event: { target: { value: string } }) => void } | undefined,
    rowActions: [...mocks.rowActions],
    rowProps: [...mocks.rowProps],
    emptyStateActions: [...mocks.emptyStateActions],
    skeletonProps: [...mocks.skeletonProps],
    jsxElements: [...mocks.jsxElements],
  };
}

beforeEach(() => {
  vi.resetModules();
  mocks.stateValues.length = 0;
  mocks.stateCursor = 0;
  mocks.navigate.mockReset();
  mocks.searchParams = new URLSearchParams();
  mocks.setSearchParams.mockReset();
  mocks.refetch.mockReset();
  mocks.createWorkflow.mockReset();
  mocks.createWorkflowAsync.mockReset();
  mocks.deleteWorkflow.mockReset();
  mocks.setWorkflowEnabled.mockReset();
  mocks.createWorkflow.mockImplementation(
    (
      _payload: unknown,
      options?: { onSuccess?: (workflow: { id: string }) => void },
    ) => {
      options?.onSuccess?.({ id: "wf_new" });
    },
  );
  mocks.createWorkflowAsync.mockResolvedValue({ id: "wf_new" });
  mocks.deleteWorkflow.mockResolvedValue({ id: "wf_research", deleted: true });
  mocks.setWorkflowEnabled.mockResolvedValue({
    id: "wf_research",
    enabled: true,
  });
  mocks.deletePending = false;
  mocks.createPending = false;
  mocks.queryState.data = {
    items: mocks.workflows,
    total: mocks.workflows.length,
  };
  mocks.queryState.isLoading = false;
  mocks.queryState.error = null;
  mocks.inputProps.length = 0;
  mocks.buttonProps.length = 0;
  mocks.rowProps.length = 0;
  mocks.emptyStateActions.length = 0;
  mocks.skeletonProps.length = 0;
  mocks.rowActions.length = 0;
  mocks.tabTriggers.length = 0;
  mocks.deleteDialogs.length = 0;
  mocks.jsxElements.length = 0;
});

describe("RUN-426 FlowsPage tabs", () => {
  const flowsSource = readFileSync(resolve(__dirname, "..", "FlowsPage.tsx"), "utf-8");

  it("renders the New Workflow header action on /flows while the workflows tab is active", () => {
    expect(flowsSource).toMatch(/New Workflow/);
    expect(flowsSource).toMatch(/PageHeader/);
  });

  it("creates an empty workflow and navigates to /workflows/:id/edit from the header action", () => {
    expect(flowsSource).toMatch(/useCreateWorkflow/);
    expect(flowsSource).toMatch(/navigate\(`\/workflows\/\$\{/);
    expect(flowsSource).toMatch(/\/edit`\)/);
  });

  it("renders Flows with the Workflows tab active by default on /flows", () => {
    expect(flowsSource).toMatch(/title="Flows"/);
    expect(flowsSource).toMatch(/value="workflows"/);
    expect(flowsSource).toMatch(/Workflows/);
    // No runs tab — workflow-only
    expect(flowsSource).not.toMatch(/value="runs"/);
  });

  it("keeps /flows workflow-only even when tab=runs is present in the URL", () => {
    // Tabs value is hardcoded to "workflows", not derived from URL params
    expect(flowsSource).toMatch(/value="workflows"/);
    expect(flowsSource).not.toMatch(/useSearchParams/);
  });

  it("keeps the header visible while the workflows tab shows loading placeholders", () => {
    // PageHeader is rendered unconditionally (outside the Tabs content)
    expect(flowsSource).toMatch(/PageHeader/);
    expect(flowsSource).toMatch(/WorkflowsTab/);
  });
});

describe("RUN-426 WorkflowsTab behavior", () => {
  it("renders the workflows collection inside a semantic list container", async () => {
    const view = await renderWorkflowsTab();

    const hasSemanticList = view.jsxElements.some(({ type, props }) => {
      if (type === "ul" || type === "ol") {
        return true;
      }

      return props.role === "list";
    });

    expect(hasSemanticList).toBe(true);
  });

  it("filters rows by workflow name case-insensitively and keeps only matching names visible", async () => {
    const firstView = await renderWorkflowsTab();

    expect(firstView.html).toContain("Research &amp; Review");
    expect(firstView.html).toContain("Content Pipeline");
    expect(firstView.html).toContain("Daily Digest");

    firstView.input?.onChange?.({ target: { value: "reSeArCh" } });

    const filteredView = await renderWorkflowsTab();

    expect(filteredView.html).toContain("Research &amp; Review");
    expect(filteredView.html).not.toContain("Content Pipeline");
    expect(filteredView.html).not.toContain("Daily Digest");
  });

  it("filters rows by workflow name and ignores description-only matches", async () => {
    const firstView = await renderWorkflowsTab();

    expect(firstView.html).toContain("Research &amp; Review");
    expect(firstView.html).toContain("Content Pipeline");
    expect(firstView.html).toContain("Daily Digest");

    firstView.input?.onChange?.({ target: { value: "schema" } });

    const filteredView = await renderWorkflowsTab();

    expect(filteredView.html).not.toContain("Research &amp; Review");
    expect(filteredView.html).not.toContain("Content Pipeline");
    expect(filteredView.html).not.toContain("Daily Digest");
    expect(filteredView.html).toContain("No workflows match your search");
  });

  it("shows a Clear search action for no-results and clears the workflow query when used", async () => {
    const firstView = await renderWorkflowsTab();

    firstView.input?.onChange?.({ target: { value: "schema" } });

    const filteredView = await renderWorkflowsTab();
    const clearSearchAction = filteredView.emptyStateActions.at(-1);

    expect(filteredView.html).toContain("No workflows match your search");
    expect(filteredView.html).toContain("Clear search");

    clearSearchAction?.onClick?.();

    const resetView = await renderWorkflowsTab();

    expect(resetView.html).toContain("Research &amp; Review");
    expect(resetView.html).toContain("Content Pipeline");
    expect(resetView.html).toContain("Daily Digest");
  });

  it("opens a workflow-specific delete confirmation dialog from the row action", async () => {
    const view = await renderWorkflowsTab();
    const researchRow = view.rowActions.find((row) => row.workflow.id === "wf_research");

    researchRow?.deleteRow?.();

    const afterDeleteClick = await renderWorkflowsTab();

    expect(afterDeleteClick.html).toContain("Delete Workflow");
    expect(afterDeleteClick.html).toContain("Research &amp; Review");
    expect(afterDeleteClick.html).toContain("This action cannot be undone");
  });

  it("renders the spec error state with retry guidance", async () => {
    mocks.queryState.error = new Error("permission denied");
    mocks.queryState.data = undefined as unknown as typeof mocks.queryState.data;

    const view = await renderWorkflowsTab();

    expect(view.html).toContain(
      "Couldn&#39;t load workflows. Check file permissions on custom/workflows/.",
    );
    expect(view.html).toContain("Retry");
  });

  it("renders the empty state with the create workflow CTA", async () => {
    mocks.queryState.data = {
      items: [],
      total: 0,
    };

    const view = await renderWorkflowsTab();

    expect(view.html).toContain("No workflows yet");
    expect(view.html).toContain(
      "Create your first workflow to start orchestrating AI agents.",
    );
    expect(view.html).toContain("Create Workflow");
  });
});
