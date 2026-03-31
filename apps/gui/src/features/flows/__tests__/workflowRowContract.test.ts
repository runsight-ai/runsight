import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fixtures = {
  populatedWorkflow: {
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
  partialWorkflow: {
    id: "wf_partial",
    name: "New Draft",
    description: "Fresh workflow with no runs",
    block_count: 2,
    modified_at: Date.parse("2026-03-28T12:00:00Z") / 1000,
    commit_sha: null,
    health: {
      run_count: 0,
      eval_pass_pct: null,
      eval_health: null,
      total_cost_usd: 0,
      regression_count: 0,
    },
  },
};

const mocks = vi.hoisted(() => ({
  stateValues: [] as unknown[],
  stateCursor: 0,
  navigate: vi.fn(),
  deleteRequests: [] as Array<unknown>,
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
  const actual = await vi.importActual<typeof import("react/jsx-runtime")>(
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
}));

vi.mock("@runsight/ui/button", () => ({
  Button: (props: Record<string, unknown>) =>
    React.createElement(
      "button",
      {
        type: "button",
        ...props,
      },
      props.children,
    ),
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

async function loadWorkflowRowComponent() {
  const module = await import("../WorkflowRow");
  return (module.Component ??
    (module as Record<string, unknown>).WorkflowRow) as React.ComponentType<Record<string, unknown>>;
}

async function renderWorkflowRow(props: Record<string, unknown>) {
  mocks.stateCursor = 0;
  mocks.jsxElements.length = 0;

  const WorkflowRow = await loadWorkflowRowComponent();
  const html = renderToStaticMarkup(React.createElement(WorkflowRow, props));

  return {
    html,
    elements: [...mocks.jsxElements],
  };
}

function findInteractiveRow(elements: Array<{ type: unknown; props: Record<string, unknown> }>) {
  return elements.find(({ props }) => {
    const ariaLabel = String(props["aria-label"] ?? "");

    return (
      typeof props.onClick === "function" &&
      typeof props.onKeyDown === "function" &&
      !ariaLabel.startsWith("Delete ")
    );
  });
}

function findDeleteButton(elements: Array<{ type: unknown; props: Record<string, unknown> }>) {
  return elements.find(({ type, props }) => {
    if (type !== "button") {
      return false;
    }

    return String(props["aria-label"] ?? "").startsWith("Delete ");
  });
}

beforeEach(() => {
  vi.resetModules();
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-03-31T12:00:00Z"));
  mocks.stateValues.length = 0;
  mocks.stateCursor = 0;
  mocks.navigate.mockReset();
  mocks.deleteRequests.length = 0;
  mocks.jsxElements.length = 0;
});

afterEach(() => {
  vi.useRealTimers();
});

describe("RUN-426 WorkflowRow behavior", () => {
  it("renders the two-line workflow content from the enhanced workflow payload", async () => {
    const view = await renderWorkflowRow({
      workflow: fixtures.populatedWorkflow,
      onDelete: (workflow: unknown) => mocks.deleteRequests.push(workflow),
    });

    expect(view.html).toContain("Research &amp; Review");
    expect(view.html).toMatch(/3 blocks?|3 block/);
    expect(view.html).toContain("f078f13");
    expect(view.html).toMatch(/12 runs?|12 run/);
    expect(view.html).toMatch(/92.*eval/);
    expect(view.html).toMatch(/\$0\.42|0\.42/);
    expect(view.html).toMatch(/0 regressions?|0 regression/);
  });

  it("uses partial-state fallbacks for workflows with no runs yet", async () => {
    const view = await renderWorkflowRow({
      workflow: fixtures.partialWorkflow,
      onDelete: (workflow: unknown) => mocks.deleteRequests.push(workflow),
    });

    expect(view.html).toContain("New Draft");
    expect(view.html).toMatch(/0 runs?|0 run/);
    expect(view.html).toMatch(/No runs yet|—/);
    expect(view.html).toMatch(/uncommitted|Uncommitted/);
  });

  it("renders each workflow as a semantic list item", async () => {
    const view = await renderWorkflowRow({
      workflow: fixtures.populatedWorkflow,
      onDelete: (workflow: unknown) => mocks.deleteRequests.push(workflow),
    });

    const hasSemanticListItem = view.elements.some(({ type, props }) => {
      if (type === "li") {
        return true;
      }

      return props.role === "listitem";
    });

    expect(hasSemanticListItem).toBe(true);
  });

  it("opens /workflows/:id/edit when the row is activated by click or keyboard", async () => {
    const firstView = await renderWorkflowRow({
      workflow: fixtures.populatedWorkflow,
      onDelete: (workflow: unknown) => mocks.deleteRequests.push(workflow),
    });
    const interactiveRow = findInteractiveRow(firstView.elements);

    interactiveRow?.props.onClick?.({ preventDefault: vi.fn() });

    expect(mocks.navigate).toHaveBeenCalledWith("/workflows/wf_research/edit");

    mocks.navigate.mockClear();

    interactiveRow?.props.onKeyDown?.({
      key: "Enter",
      preventDefault: vi.fn(),
    });

    expect(mocks.navigate).toHaveBeenCalledWith("/workflows/wf_research/edit");
  });

  it("exposes an accessible trash control and keeps it available on focus", async () => {
    const firstView = await renderWorkflowRow({
      workflow: fixtures.populatedWorkflow,
      onDelete: (workflow: unknown) => mocks.deleteRequests.push(workflow),
    });
    const interactiveRow = findInteractiveRow(firstView.elements);
    let deleteButton = findDeleteButton(firstView.elements);

    if (!deleteButton) {
      interactiveRow?.props.onFocus?.({ preventDefault: vi.fn() });
      interactiveRow?.props.onMouseEnter?.({ preventDefault: vi.fn() });

      const focusedView = await renderWorkflowRow({
        workflow: fixtures.populatedWorkflow,
        onDelete: (workflow: unknown) => mocks.deleteRequests.push(workflow),
      });

      deleteButton = findDeleteButton(focusedView.elements);
    }

    expect(deleteButton).toBeDefined();
    expect(String(deleteButton?.props["aria-label"] ?? "")).toContain(
      "Delete Research & Review workflow",
    );
  });
});
