// @vitest-environment jsdom

import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Outlet } from "react-router";

/* ------------------------------------------------------------------ */
/*  Mock data                                                          */
/* ------------------------------------------------------------------ */

const mocks = vi.hoisted(() => ({
  productionRuns: [
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
      regression_count: 3,
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
      regression_count: 0,
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
      regression_count: null,
      created_at: 1_774_407_199,
    },
  ],
  attentionItems: {
    items: [
      {
        run_id: "run_research_7",
        workflow_id: "wf_research",
        type: "assertion_regression",
        title: "Research & Review · score",
        description: "Eval failed on the latest production run.",
      },
      {
        run_id: "run_pipeline_12",
        workflow_id: "wf_pipeline",
        type: "quality_drop",
        title: "Content Pipeline · score",
        description: "Eval score dropped vs the previous production run.",
      },
    ] as Array<Record<string, unknown>>,
  },
  runsQueryCalls: [] as unknown[],
  refetchRuns: vi.fn(),
  runsQueryState: {
    data: null as {
      items: Array<Record<string, unknown>>;
      total: number;
      offset: number;
      limit: number;
    } | null,
    isLoading: false,
    error: null as Error | null,
  },
}));

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function normalizeSources(params: unknown): string[] {
  if (params instanceof URLSearchParams) {
    return params.getAll("source").sort();
  }

  if (
    params &&
    typeof params === "object" &&
    "source" in params &&
    Array.isArray((params as { source?: unknown }).source)
  ) {
    return [...((params as { source: string[] }).source)].sort();
  }

  return [];
}

function getWorkflowParam(params: unknown): string | null {
  if (params instanceof URLSearchParams) {
    return params.get("workflow") ?? params.get("workflow_id");
  }

  if (params && typeof params === "object") {
    const record = params as Record<string, unknown>;

    if (typeof record.workflow === "string") {
      return record.workflow;
    }

    if (typeof record.workflow_id === "string") {
      return record.workflow_id;
    }
  }

  return null;
}

function getStatusParams(params: unknown): string[] {
  if (params instanceof URLSearchParams) {
    return params.getAll("status");
  }

  if (params && typeof params === "object") {
    const record = params as Record<string, unknown>;
    if (Array.isArray(record.status)) {
      return record.status.filter((value): value is string => typeof value === "string");
    }
    if (typeof record.status === "string") {
      return [record.status];
    }
  }

  return [];
}

function getBranchParam(params: unknown): string | null {
  if (params instanceof URLSearchParams) {
    return params.get("branch");
  }

  if (params && typeof params === "object") {
    const record = params as Record<string, unknown>;
    return typeof record.branch === "string" ? record.branch : null;
  }

  return null;
}

function buildRunList(items: Array<Record<string, unknown>>) {
  return {
    items,
    total: items.length,
    offset: 0,
    limit: 20,
  };
}

/* ------------------------------------------------------------------ */
/*  Mocks                                                              */
/* ------------------------------------------------------------------ */

vi.mock("@/queries/runs", () => ({
  useRuns: (params?: unknown) => {
    mocks.runsQueryCalls.push(params);
    const requestedSources = normalizeSources(params);
    const workflowId = getWorkflowParam(params);
    const statuses = getStatusParams(params);

    let items = requestedSources.length === 0
      ? [...mocks.productionRuns]
      : [...mocks.productionRuns];

    // Simulate server-side workflow filtering
    if (workflowId) {
      items = items.filter((r) => r.workflow_id === workflowId);
    }

    if (statuses.includes("running") || statuses.includes("pending")) {
      items = items.filter((r) => ["running", "pending"].includes(String(r.status)));
    }

    return {
      data: mocks.runsQueryState.data ?? buildRunList(items),
      isLoading: mocks.runsQueryState.isLoading,
      error: mocks.runsQueryState.error,
      refetch: mocks.refetchRuns,
    };
  },
  useRunRegressions: (runId?: string) => ({
    data: runId
      ? {
          count: 0,
          issues: [],
        }
      : undefined,
  }),
}));

vi.mock("@/queries/dashboard", () => ({
  useAttentionItems: () => ({ data: mocks.attentionItems }),
}));

vi.mock("@runsight/ui/skeleton", () => ({
  Skeleton: (props: Record<string, unknown>) =>
    React.createElement("div", {
      ...props,
      "data-testid": "shared-skeleton",
      "data-slot": "skeleton",
    }),
}));

vi.mock("../../../routes/guards", () => ({
  createSetupGuardLoader: () => async () => null,
  createReverseGuardLoader: () => async () => null,
}));

vi.mock("../../../routes/layouts/ShellLayout", () => ({
  ShellLayout: () => React.createElement(Outlet),
}));

vi.mock("@/queries/workflows", () => ({
  useWorkflows: () => ({
    data: {
      items: [
        { id: "wf_research", name: "Research & Review" },
        { id: "wf_pipeline", name: "Content Pipeline" },
        { id: "wf_docs", name: "Daily Digest" },
      ],
      total: 3,
    },
    isLoading: false,
    error: null,
  }),
  useWorkflowRegressions: () => ({ data: undefined }),
}));

vi.mock("@/lib/queryClient", () => ({
  queryClient: {},
}));

/* ------------------------------------------------------------------ */
/*  Lifecycle                                                          */
/* ------------------------------------------------------------------ */

let activeRouter: { dispose?: () => void; state?: { location: Location } } | null = null;

afterEach(() => {
  cleanup();
  activeRouter?.dispose?.();
  activeRouter = null;
  window.history.pushState({}, "", "/");
});

beforeEach(() => {
  mocks.runsQueryCalls.length = 0;
  mocks.refetchRuns.mockReset();
  mocks.runsQueryState.data = null;
  mocks.runsQueryState.isLoading = false;
  mocks.runsQueryState.error = null;
  mocks.attentionItems.items = [
    {
      run_id: "run_research_7",
      workflow_id: "wf_research",
      type: "assertion_regression",
      title: "Research & Review · score",
      description: "Eval failed on the latest production run.",
    },
    {
      run_id: "run_pipeline_12",
      workflow_id: "wf_pipeline",
      type: "quality_drop",
      title: "Content Pipeline · score",
      description: "Eval score dropped vs the previous production run.",
    },
  ];
});

/* ------------------------------------------------------------------ */
/*  Render helper                                                      */
/* ------------------------------------------------------------------ */

async function renderRunsRoute(initialPath = "/runs") {
  vi.resetModules();
  window.history.pushState({}, "", initialPath);

  const { RouterProvider } = await import("react-router");
  const { router } = await import("../../../routes");

  activeRouter = router;
  const user = userEvent.setup();
  render(React.createElement(RouterProvider, { router }));

  return { router, user };
}

function getVisibleColumnHeaders() {
  const table = screen.getByRole("table");
  return within(table)
    .getAllByRole("columnheader")
    .map((th) => th.textContent?.trim() ?? "");
}

function getVisibleWorkflowOrder() {
  const table = screen.getByRole("table");
  return within(table)
    .getAllByRole("row")
    .slice(1)
    .map((row) => within(row).getAllByRole("cell")[1]?.textContent ?? "");
}

function findRunRow(workflowName: string) {
  const table = screen.getByRole("table");
  return within(table)
    .getAllByRole("row")
    .find((row) => within(row).queryByText(workflowName));
}

function getCellsInColumn(columnName: string): HTMLElement[] {
  const table = screen.getByRole("table");
  const headers = within(table).getAllByRole("columnheader");
  const colIndex = headers.findIndex(
    (th) => th.textContent?.trim() === columnName,
  );

  if (colIndex === -1) {
    return [];
  }

  return within(table)
    .getAllByRole("row")
    .slice(1) // skip header row
    .map((row) => within(row).getAllByRole("cell")[colIndex])
    .filter(Boolean);
}

/* ================================================================== */
/*  AC 1: ?workflow=:id query param pre-filters runs                   */
/* ================================================================== */

describe("RUN-562 workflow filter via query param", () => {
  it("passes workflow_id to useRuns when ?workflow=:id is present in the URL", async () => {
    await renderRunsRoute("/runs?workflow=wf_research");

    await waitFor(() => {
      const lastCall = mocks.runsQueryCalls.at(-1);
      expect(getWorkflowParam(lastCall)).toBe("wf_research");
    });
  });

  it("shows only runs for the filtered workflow when ?workflow param is set", async () => {
    await renderRunsRoute("/runs?workflow=wf_research");

    await waitFor(() => {
      const table = screen.getByRole("table");
      const rows = within(table).getAllByRole("row").slice(1);
      expect(rows).toHaveLength(1);
    });

    expect(screen.getAllByText("Research & Review").length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText("Content Pipeline")).toBeNull();
    expect(screen.queryByText("Daily Digest")).toBeNull();
  });

  it("does not pass workflow_id to useRuns when no ?workflow param is present", async () => {
    await renderRunsRoute("/runs");

    await waitFor(() => {
      const lastCall = mocks.runsQueryCalls.at(-1);
      expect(getWorkflowParam(lastCall)).toBeNull();
    });
  });
});

/* ================================================================== */
/*  AC 2: header shows "Runs — [Name]" with × clear button            */
/* ================================================================== */

describe("RUN-562 filtered page header", () => {
  it('shows "Runs — [Workflow Name]" in the header when workflow filter is active', async () => {
    await renderRunsRoute("/runs?workflow=wf_research");

    const heading = await screen.findByRole("heading", { level: 1 });
    expect(heading.textContent).toContain("Research & Review");
  });

  it("shows a clear (×) button in the header when workflow filter is active", async () => {
    await renderRunsRoute("/runs?workflow=wf_research");

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 }).textContent).toContain(
        "Research & Review",
      );
    });

    // The clear button should be findable — it removes the workflow filter
    const clearButton = screen.getByRole("button", { name: /clear/i });
    expect(clearButton).toBeTruthy();
  });

  it("removes the workflow query param and restores plain 'Runs' header when × is clicked", async () => {
    const { router, user } = await renderRunsRoute("/runs?workflow=wf_research");

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 }).textContent).toContain(
        "Research & Review",
      );
    });

    const clearButton = screen.getByRole("button", { name: /clear/i });
    await user.click(clearButton);

    await waitFor(() => {
      const heading = screen.getByRole("heading", { level: 1 });
      expect(heading.textContent).not.toContain("Research & Review");
      expect(heading.textContent).toContain("Runs");
    });

    // URL should no longer have the workflow param
    expect(router.state?.location.search).not.toContain("workflow=");
  });

  it('shows the plain "Runs" header with no clear button when no workflow filter is active', async () => {
    await renderRunsRoute("/runs");

    const heading = await screen.findByRole("heading", { level: 1 });
    expect(heading.textContent).toBe("Runs");
    expect(screen.queryByRole("button", { name: /clear/i })).toBeNull();
  });

  it('shows "Runs — Attention" when the attention filter is active', async () => {
    await renderRunsRoute("/runs?attention=only");

    const heading = await screen.findByRole("heading", { level: 1 });
    expect(heading.textContent).toBe("Runs — Attention");
  });

  it("lets the user toggle the attention filter directly from the runs page", async () => {
    const { router, user } = await renderRunsRoute("/runs");

    const attentionButton = await screen.findByRole("button", {
      name: "Needs attention",
    });

    await user.click(attentionButton);

    await waitFor(() => {
      expect(router.state?.location.search).toContain("attention=only");
      expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(
        "Runs — Attention",
      );
    });

    await user.click(screen.getByRole("button", { name: "Needs attention" }));

    await waitFor(() => {
      expect(router.state?.location.search).not.toContain("attention=only");
      expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Runs");
    });
  });

  it("filters runs using regression_count > 0 for the attention feed", async () => {
    await renderRunsRoute("/runs?attention=only");

    await waitFor(() => {
      // Only Research & Review has regression_count: 3 — it should appear
      expect(screen.getByText("Research & Review")).toBeTruthy();
    });

    // Content Pipeline (regression_count: 0) and Daily Digest (null) should be filtered out
    expect(screen.queryByText("Content Pipeline")).toBeNull();
    expect(screen.queryByText("Daily Digest")).toBeNull();
  });

  it('shows "Runs — Active" when the active filter is active', async () => {
    await renderRunsRoute("/runs?status=active");

    const heading = await screen.findByRole("heading", { level: 1 });
    expect(heading.textContent).toBe("Runs — Active");
  });

  it("lets the user toggle the active filter directly from the runs page", async () => {
    const { router, user } = await renderRunsRoute("/runs");

    const activeButton = await screen.findByRole("button", {
      name: "Active",
    });

    await user.click(activeButton);

    await waitFor(() => {
      expect(router.state?.location.search).toContain("status=active");
      expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(
        "Runs — Active",
      );
    });

    await user.click(screen.getByRole("button", { name: "Active" }));

    await waitFor(() => {
      expect(router.state?.location.search).not.toContain("status=active");
      expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Runs");
    });
  });

  it("passes branch=main when the active filter is active", async () => {
    await renderRunsRoute("/runs?status=active");

    await waitFor(() => {
      const lastCall = mocks.runsQueryCalls.at(-1);
      expect(getStatusParams(lastCall)).toEqual(["running", "pending"]);
      expect(getBranchParam(lastCall)).toBe("main");
    });
  });
});

/* ================================================================== */
/*  AC 3: Warnings column shows per-run regression count with ⚠ badge */
/* ================================================================== */

describe("RUN-562 Warnings column regression display", () => {
  it('renders a "Warnings" column header after Eval', async () => {
    await renderRunsRoute("/runs");

    await waitFor(() => {
      expect(screen.getByRole("table")).toBeTruthy();
    });

    const headers = getVisibleColumnHeaders();
    const evalIndex = headers.indexOf("Eval");
    expect(evalIndex).toBeGreaterThanOrEqual(0);
    expect(headers[evalIndex + 1]).toBe("Warnings");
  });

  it("displays regression count with ⚠ badge when regression_count > 0", async () => {
    await renderRunsRoute("/runs");

    const researchRow = await waitFor(() => {
      const row = findRunRow("Research & Review");
      expect(row).toBeTruthy();
      return row as HTMLElement;
    });

    // Research & Review has regression_count: 3
    expect(within(researchRow).getByText(/3/)).toBeTruthy();
    expect(researchRow.querySelector("svg")).toBeTruthy();
  });

  /* ================================================================ */
  /*  AC 5: Empty regressions show "—"                                 */
  /* ================================================================ */

  it('displays "—" when regression_count is 0', async () => {
    await renderRunsRoute("/runs");

    await waitFor(() => {
      const row = findRunRow("Content Pipeline");
      expect(row).toBeTruthy();
      return row as HTMLElement;
    });

    // Content Pipeline has regression_count: 0
    // The Warnings column cell should show a dash.
    const warningsCells = getCellsInColumn("Warnings");
    const pipelineWarningsCell = warningsCells[1]; // second row (pipeline is index 1 sorted by started desc)
    expect(pipelineWarningsCell.textContent).toBe("—");
  });

  it('displays "—" when regression_count is null', async () => {
    await renderRunsRoute("/runs");

    await waitFor(() => {
      expect(findRunRow("Daily Digest")).toBeTruthy();
    });

    // Daily Digest has regression_count: null
    const warningsCells = getCellsInColumn("Warnings");
    // Find the cell for Daily Digest (last by started_at desc)
    const digestWarningsCell = warningsCells[2];
    expect(digestWarningsCell.textContent).toBe("—");
  });
});

/* ================================================================== */
/*  AC 4: Warnings column is sortable                                  */
/* ================================================================== */

describe("RUN-562 Warnings column sorting", () => {
  it("supports ascending sort on the Warnings column", async () => {
    const { user } = await renderRunsRoute("/runs");

    const warningsHeader = await waitFor(() => {
      const header = screen.getByRole("columnheader", { name: "Warnings" });
      expect(header).toBeTruthy();
      return header;
    });

    await user.click(warningsHeader);

    expect(warningsHeader.getAttribute("aria-sort")).toBe("ascending");
  });

  it("toggles to descending sort on the Warnings column on second click", async () => {
    const { user } = await renderRunsRoute("/runs");

    const warningsHeader = await waitFor(() => {
      const header = screen.getByRole("columnheader", { name: "Warnings" });
      expect(header).toBeTruthy();
      return header;
    });

    await user.click(warningsHeader);
    await user.click(warningsHeader);

    expect(warningsHeader.getAttribute("aria-sort")).toBe("descending");
  });

  it("sorts runs by combined warning/regression count in ascending order", async () => {
    const { user } = await renderRunsRoute("/runs");

    const warningsHeader = await waitFor(() => {
      const header = screen.getByRole("columnheader", { name: "Warnings" });
      expect(header).toBeTruthy();
      return header;
    });

    await user.click(warningsHeader);

    const order = getVisibleWorkflowOrder();
    // ascending: 0 (Content Pipeline), 0 (Daily Digest), 3 (Research & Review)
    expect(order).toEqual([
      "Content Pipeline",
      "Daily Digest",
      "Research & Review",
    ]);
  });

  it("sorts runs by combined warning/regression count in descending order", async () => {
    const { user } = await renderRunsRoute("/runs");

    const warningsHeader = await waitFor(() => {
      const header = screen.getByRole("columnheader", { name: "Warnings" });
      expect(header).toBeTruthy();
      return header;
    });

    await user.click(warningsHeader);
    await user.click(warningsHeader);

    const order = getVisibleWorkflowOrder();
    // descending: 3 (Research & Review), 0 (Content Pipeline), 0 (Daily Digest)
    expect(order).toEqual([
      "Research & Review",
      "Content Pipeline",
      "Daily Digest",
    ]);
  });
});
