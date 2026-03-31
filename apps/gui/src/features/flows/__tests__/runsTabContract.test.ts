import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import type * as ReactJsxRuntime from "react/jsx-runtime";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  runs: [
    {
      id: "run_research_7",
      workflow_id: "wf_research",
      workflow_name: "Research & Review",
      run_number: 7,
      status: "completed",
      commit_sha: "f078f13deadbeef",
      source: "manual",
      branch: "main",
      started_at: 1_774_414_400,
      completed_at: 1_774_414_412,
      duration_seconds: 12.3,
      total_cost_usd: 0.04,
      total_tokens: 1200,
      eval_pass_pct: 92,
      created_at: 1_774_414_399,
    },
    {
      id: "run_pipeline_12",
      workflow_id: "wf_pipeline",
      workflow_name: "Content Pipeline",
      run_number: 12,
      status: "failed",
      commit_sha: "a463263feedbeef",
      source: "webhook",
      branch: "main",
      started_at: 1_774_410_800,
      completed_at: 1_774_410_808,
      duration_seconds: 8.1,
      total_cost_usd: 0.02,
      total_tokens: 900,
      eval_pass_pct: 75,
      created_at: 1_774_410_799,
    },
    {
      id: "run_digest_3",
      workflow_id: "wf_docs",
      workflow_name: "Daily Digest",
      run_number: 3,
      status: "completed",
      commit_sha: "705ebea99999999",
      source: "schedule",
      branch: "main",
      started_at: 1_774_407_200,
      completed_at: 1_774_407_209,
      duration_seconds: 9.2,
      total_cost_usd: 0.03,
      total_tokens: 640,
      eval_pass_pct: null,
      created_at: 1_774_407_199,
    },
  ],
  stateValues: [] as unknown[],
  stateCursor: 0,
  searchParams: new URLSearchParams(),
  setSearchParams: vi.fn(),
  navigate: vi.fn(),
  refetchRuns: vi.fn(),
  createWorkflow: vi.fn(),
  createWorkflowAsync: vi.fn(),
  runsQueryCalls: [] as unknown[],
  runsQueryState: {
    data: {
      items: [] as Array<Record<string, unknown>>,
      total: 0,
      offset: 0,
      limit: 20,
    },
    isLoading: false,
    error: null as Error | null,
  },
  inputProps: [] as Array<Record<string, unknown>>,
  buttonProps: [] as Array<Record<string, unknown>>,
  tabTriggers: [] as Array<{ value: string; disabled: boolean; active: boolean; onClick?: () => void }>,
  rowProps: [] as Array<Record<string, unknown>>,
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
  useCreateWorkflow: () => ({
    mutate: mocks.createWorkflow,
    mutateAsync: mocks.createWorkflowAsync,
    isPending: false,
  }),
}));

vi.mock("@/queries/runs", () => ({
  useRuns: (params?: unknown) => {
    mocks.runsQueryCalls.push(params);

    return {
      data: mocks.runsQueryState.data,
      isLoading: mocks.runsQueryState.isLoading,
      error: mocks.runsQueryState.error,
      refetch: mocks.refetchRuns,
    };
  },
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

vi.mock("@runsight/ui/tabs", async () => {
  const actualReact = await vi.importActual<typeof React>("react");
  const TabsContext = actualReact.createContext<{
    value: string;
    onValueChange?: (value: string) => void;
  }>({ value: "" });

  return {
    Tabs: ({
      value,
      defaultValue,
      onValueChange,
      children,
    }: {
      value?: string;
      defaultValue?: string;
      onValueChange?: (value: string) => void;
      children: React.ReactNode;
    }) =>
      actualReact.createElement(
        TabsContext.Provider,
        {
          value: {
            value: value ?? defaultValue ?? "",
            onValueChange,
          },
        },
        actualReact.createElement("div", null, children),
      ),
    TabsList: ({ children, ...props }: Record<string, unknown>) =>
      actualReact.createElement("div", props, children),
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
      const context = actualReact.useContext(TabsContext);
      const active = context.value === value;
      const onClick = () => {
        if (!disabled) {
          context.onValueChange?.(value);
        }
      };

      mocks.tabTriggers.push({
        value,
        disabled: Boolean(disabled),
        active,
        onClick,
      });

      return actualReact.createElement(
        "button",
        {
          type: "button",
          role: "tab",
          "aria-selected": active,
          "aria-disabled": disabled ? "true" : "false",
          disabled,
          onClick,
          ...props,
        },
        children,
      );
    },
    TabsContent: ({
      value,
      children,
      ...props
    }: {
      value: string;
      children: React.ReactNode;
    }) => {
      const context = actualReact.useContext(TabsContext);

      if (context.value !== value) {
        return null;
      }

      return actualReact.createElement("section", props, children);
    },
  };
});

vi.mock("@runsight/ui/table", () => ({
  Table: ({ children, ...props }: Record<string, unknown>) =>
    React.createElement("table", props, children),
  TableHeader: ({ children, ...props }: Record<string, unknown>) =>
    React.createElement("thead", props, children),
  TableBody: ({ children, ...props }: Record<string, unknown>) =>
    React.createElement("tbody", props, children),
  TableRow: (props: Record<string, unknown>) => {
    mocks.rowProps.push(props);
    return React.createElement("tr", props, props.children);
  },
  TableHead: ({ children, ...props }: Record<string, unknown>) =>
    React.createElement("th", { scope: "col", ...props }, children),
  TableCell: ({ children, ...props }: Record<string, unknown>) =>
    React.createElement("td", props, children),
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
  }) =>
    React.createElement("section", null, [
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
    ]),
}));

vi.mock("../WorkflowsTab", () => ({
  WorkflowsTab: () =>
    React.createElement("section", { "data-testid": "workflows-tab" }, "Workflows tab shell"),
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

async function loadFlowsPageComponent() {
  const module = await import("../FlowsPage");
  return (module.Component ?? (module as Record<string, unknown>).FlowsPage) as React.ComponentType;
}

function getTextContent(value: React.ReactNode): string {
  return React.Children.toArray(value)
    .flatMap((child) => {
      if (typeof child === "string" || typeof child === "number") {
        return [String(child)];
      }

      if (React.isValidElement(child)) {
        return [getTextContent(child.props.children)];
      }

      return [];
    })
    .join(" ")
    .replace(/\s+/g, " ")
    .trim();
}

function findRenderedButton(label: string) {
  return mocks.jsxElements.find(
    ({ type, props }) => type === "button" && getTextContent(props.children as React.ReactNode) === label,
  )?.props as { onClick?: () => void } | undefined;
}

function expectProductionSourceFilter(params: unknown) {
  let sources: string[] = [];

  if (params instanceof URLSearchParams) {
    sources = params.getAll("source");
  } else if (params && typeof params === "object") {
    const rawSource = (params as { source?: string | string[] }).source;

    if (Array.isArray(rawSource)) {
      sources = rawSource;
    } else if (typeof rawSource === "string") {
      sources = rawSource.split(",").map((value) => value.trim());
    }
  }

  expect(sources).toEqual(
    expect.arrayContaining(["manual", "webhook", "schedule"]),
  );
  expect(sources).not.toContain("simulation");
}

function countRunSkeletons(elements: Array<{ type: unknown; props: Record<string, unknown> }>) {
  return elements.filter(({ type, props }) => {
    if (type !== "div" && type !== "tr") {
      return false;
    }

    const className = String(props.className ?? "");

    return (
      props["data-testid"] === "run-skeleton-row" ||
      props["aria-label"] === "Loading run row" ||
      /\brun-skeleton-row\b/.test(className) ||
      (/\banimate-pulse\b/.test(className) && /\b(round|rounded|border)\b/.test(className))
    );
  }).length;
}

async function renderFlowsPage() {
  mocks.stateCursor = 0;
  mocks.inputProps.length = 0;
  mocks.buttonProps.length = 0;
  mocks.tabTriggers.length = 0;
  mocks.rowProps.length = 0;
  mocks.jsxElements.length = 0;
  mocks.runsQueryCalls.length = 0;

  const FlowsPage = await loadFlowsPageComponent();
  const html = renderToStaticMarkup(React.createElement(FlowsPage));

  return {
    html,
    input: mocks.inputProps.at(-1) as { onChange?: (event: { target: { value: string } }) => void } | undefined,
    tabTriggers: [...mocks.tabTriggers],
    rowProps: [...mocks.rowProps],
    jsxElements: [...mocks.jsxElements],
    runsQueryCalls: [...mocks.runsQueryCalls],
  };
}

beforeEach(() => {
  vi.resetModules();
  mocks.stateValues.length = 0;
  mocks.stateCursor = 0;
  mocks.searchParams = new URLSearchParams();
  mocks.setSearchParams.mockReset();
  mocks.navigate.mockReset();
  mocks.refetchRuns.mockReset();
  mocks.createWorkflow.mockReset();
  mocks.createWorkflowAsync.mockReset();
  mocks.runsQueryCalls.length = 0;
  mocks.runsQueryState.data = {
    items: mocks.runs,
    total: mocks.runs.length,
    offset: 0,
    limit: 20,
  };
  mocks.runsQueryState.isLoading = false;
  mocks.runsQueryState.error = null;
  mocks.inputProps.length = 0;
  mocks.buttonProps.length = 0;
  mocks.tabTriggers.length = 0;
  mocks.rowProps.length = 0;
  mocks.jsxElements.length = 0;
});

describe("RUN-427 FlowsPage runs tab", () => {
  it("uses /flows?tab=runs as URL-driven state and hides the New Workflow header action", async () => {
    mocks.searchParams = new URLSearchParams("tab=runs");

    const view = await renderFlowsPage();
    const runsTab = view.tabTriggers.find((tab) => tab.value === "runs");
    const workflowsTab = view.tabTriggers.find((tab) => tab.value === "workflows");

    expect(view.html).toContain("Flows");
    expect(runsTab?.active).toBe(true);
    expect(workflowsTab?.active).toBe(false);
    expect(view.html).not.toContain("New Workflow");
    expect(view.html).not.toContain("Workflows tab shell");
    expect(view.runsQueryCalls).toHaveLength(1);
    expectProductionSourceFilter(view.runsQueryCalls[0]);
  });

  it("updates the /flows tab query param when the user activates the Runs tab", async () => {
    const firstView = await renderFlowsPage();
    const runsTab = firstView.tabTriggers.find((tab) => tab.value === "runs");

    runsTab?.onClick?.();

    expect(mocks.setSearchParams).toHaveBeenCalledTimes(1);
    expect(mocks.setSearchParams.mock.calls[0]?.[0]).toBeInstanceOf(URLSearchParams);
    expect((mocks.setSearchParams.mock.calls[0]?.[0] as URLSearchParams).get("tab")).toBe("runs");
  });

  it("renders an 8-column runs table with run_number and eval_pass_pct, including partial rows", async () => {
    mocks.searchParams = new URLSearchParams("tab=runs");

    const view = await renderFlowsPage();

    for (const heading of [
      "Status",
      "Workflow",
      "Run",
      "Commit",
      "Duration",
      "Cost",
      "Eval",
      "Started",
    ]) {
      expect(view.html).toContain(heading);
    }

    expect(view.html).toContain("Research &amp; Review");
    expect(view.html).toContain("#7");
    expect(view.html).toContain("92%");
    expect(view.html).toContain("Daily Digest");
    expect(view.html).toContain("—");
  });

  it("filters runs by workflow name case-insensitively", async () => {
    mocks.searchParams = new URLSearchParams("tab=runs");

    const firstView = await renderFlowsPage();

    expect(firstView.html).toContain("Research &amp; Review");
    expect(firstView.html).toContain("Content Pipeline");
    expect(firstView.html).toContain("Daily Digest");

    firstView.input?.onChange?.({ target: { value: "reSeArCh" } });

    const filteredView = await renderFlowsPage();

    expect(filteredView.html).toContain("Research &amp; Review");
    expect(filteredView.html).not.toContain("Content Pipeline");
    expect(filteredView.html).not.toContain("Daily Digest");
  });

  it("marks Started as the default descending sort and lets the user sort by Workflow", async () => {
    mocks.searchParams = new URLSearchParams("tab=runs");

    const firstView = await renderFlowsPage();

    expect(firstView.html).toContain('aria-sort="descending"');

    const workflowSortButton = findRenderedButton("Workflow");
    workflowSortButton?.onClick?.();

    const sortedView = await renderFlowsPage();

    expect(sortedView.html).toContain('aria-sort="ascending"');
    expect(sortedView.html.indexOf("Content Pipeline")).toBeLessThan(
      sortedView.html.indexOf("Research &amp; Review"),
    );
  });

  it("opens the workflow editor when a runs-table row is activated", async () => {
    mocks.searchParams = new URLSearchParams("tab=runs");

    const view = await renderFlowsPage();
    const firstClickableRow = view.rowProps.find(
      (props) => typeof props.onClick === "function",
    ) as { onClick: () => void } | undefined;

    firstClickableRow?.onClick();

    expect(mocks.navigate).toHaveBeenCalledWith("/workflows/wf_research/edit");
  });

  it("keeps the Flows header visible while the Runs tab shows five loading skeleton rows", async () => {
    mocks.searchParams = new URLSearchParams("tab=runs");
    mocks.runsQueryState.isLoading = true;
    mocks.runsQueryState.data = undefined as unknown as typeof mocks.runsQueryState.data;

    const view = await renderFlowsPage();

    expect(view.html).toContain("Flows");
    expect(view.html).not.toContain("New Workflow");
    expect(countRunSkeletons(view.jsxElements)).toBeGreaterThanOrEqual(5);
  });

  it("renders the runs error state with retry guidance", async () => {
    mocks.searchParams = new URLSearchParams("tab=runs");
    mocks.runsQueryState.error = new Error("runs unavailable");
    mocks.runsQueryState.data = undefined as unknown as typeof mocks.runsQueryState.data;

    const view = await renderFlowsPage();

    expect(view.html).toContain("Couldn&#39;t load runs.");
    expect(view.html).toContain("Retry");
  });

  it("renders the empty runs state with a Go to Workflows action", async () => {
    mocks.searchParams = new URLSearchParams("tab=runs");
    mocks.runsQueryState.data = {
      items: [],
      total: 0,
      offset: 0,
      limit: 20,
    };

    const view = await renderFlowsPage();

    expect(view.html).toContain("No runs yet");
    expect(view.html).toContain("Run a workflow to see execution history here.");
    expect(view.html).toContain("Go to Workflows");
  });
});
