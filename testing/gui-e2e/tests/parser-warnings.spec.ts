import { expect, test, type Page } from "@playwright/test";

import {
  API,
  apiGet,
  apiPost,
  gotoShellRoute,
  setupShellReadyWorkspace,
} from "./helpers/shellReady";

test.describe.configure({ mode: "serial" });
setupShellReadyWorkspace(test);

type WarningItem = {
  message: string;
  source?: string | null;
  context?: string | null;
};

type RunNodeSummary = {
  total: number;
  completed: number;
  running: number;
  pending: number;
  failed: number;
};

type RunListItem = {
  id: string;
  workflow_id: string;
  workflow_name: string;
  status: string;
  total_cost_usd: number;
  total_tokens: number;
  created_at: number;
  branch: string;
  source: string;
  commit_sha?: string | null;
  run_number?: number | null;
  eval_pass_pct?: number | null;
  eval_score_avg?: number | null;
  regression_count?: number | null;
  warnings: WarningItem[];
  node_summary?: RunNodeSummary | null;
  [key: string]: unknown;
};

type RunListResponse = {
  items: RunListItem[];
  total: number;
  offset: number;
  limit: number;
};

type WorkflowResponse = {
  id: string;
  kind: "workflow";
  name?: string | null;
};

type WorkflowSimulationResponse = {
  branch: string;
  commit_sha: string;
};

const CANVAS_STATE = {
  nodes: [],
  edges: [],
  viewport: { x: 0, y: 0, zoom: 1 },
  selected_node_id: null,
  canvas_mode: "dag" as const,
};

let warningSoulId = "";
let warningWorkflowId = "";
let warningWorkflowName = "";
let warningRunId = "";
let warningRunListItem: RunListItem | null = null;

function warningWorkflowYaml(workflowId: string, soulId: string, workflowName: string) {
  return `version: "1.0"
id: ${workflowId}
kind: workflow
config:
  model_name: gpt-4o
blocks:
  analyze:
    type: linear
    soul_ref: ${soulId}
workflow:
  name: ${workflowName}
  entry: analyze
  transitions:
    - from: analyze
      to: null
`;
}

async function safeDelete(apiPath: string) {
  await fetch(`${API}${apiPath}`, { method: "DELETE" });
}

function rowForWorkflow(page: Page, workflowName: string) {
  return page.locator("tbody tr").filter({ hasText: workflowName }).first();
}

test.describe("RUN-845 parser warnings browser flows", () => {
  test.beforeAll(async () => {
    const suffix = Date.now().toString(36);
    warningSoulId = `run845-warning-soul-${suffix}`;
    warningWorkflowId = `run845-warning-flow-${suffix}`;
    warningWorkflowName = `RUN-845 warning flow ${suffix}`;

    await apiPost("/souls", {
      id: warningSoulId,
      kind: "soul",
      name: "RUN-845 Warning Soul",
      role: "RUN-845 Warning Soul",
      system_prompt: "Parser warning soul for e2e coverage.",
      tools: ["http"],
      provider: "openai",
      model_name: "gpt-4.1-mini",
    });

    const workflow = await apiPost<WorkflowResponse>("/workflows", {
      name: warningWorkflowName,
      yaml: warningWorkflowYaml(warningWorkflowId, warningSoulId, warningWorkflowName),
      canvas_state: CANVAS_STATE,
      commit: false,
    });
    warningWorkflowId = workflow.id;

    const simulation = await apiPost<WorkflowSimulationResponse>(
      `/workflows/${warningWorkflowId}/simulations`,
      { yaml: warningWorkflowYaml(warningWorkflowId, warningSoulId, warningWorkflowName) },
    );
    const createdRun = await apiPost<{ id: string; warnings: WarningItem[] }>("/runs", {
      workflow_id: warningWorkflowId,
      task_data: { instruction: "Exercise parser warnings" },
      source: "simulation",
      branch: simulation.branch,
    });
    warningRunId = createdRun.id;

    await expect
      .poll(async () => {
        const runs = await apiGet<RunListResponse>("/runs");
        const item = runs.items.find((run) => run.id === warningRunId);
        return item?.warnings?.length ?? 0;
      })
      .toBeGreaterThan(0);

    const runs = await apiGet<RunListResponse>("/runs");
    warningRunListItem = runs.items.find((run) => run.id === warningRunId) ?? null;
  });

  test.afterAll(async () => {
    if (warningWorkflowId) {
      await safeDelete(`/workflows/${warningWorkflowId}?force=true`);
    }
    if (warningSoulId) {
      await safeDelete(`/souls/${warningSoulId}`);
    }
  });

  test("runs page shows warning badge/tooltip, warnings column, and warning-only runs in Needs attention", async ({
    page,
  }) => {
    await gotoShellRoute(page, "/runs");

    await expect(page.getByRole("columnheader", { name: "Warnings" })).toBeVisible();

    const warningRow = rowForWorkflow(page, warningWorkflowName);
    await expect(warningRow).toBeVisible();

    const warningBadge = warningRow.getByRole("status", { name: /warning/i });
    await expect(warningBadge).toBeVisible();

    await warningBadge.hover();
    await expect(page.getByText("1 warning")).toBeVisible();
    await expect(page.getByText(/undeclared tool/i)).toBeVisible();

    await page.getByRole("button", { name: "Needs attention" }).click();
    await expect(page).toHaveURL(/attention=only/);
    await expect(warningRow).toBeVisible();
    await expect(warningBadge).toBeVisible();

    await expect(warningRow.locator("td").first()).not.toHaveClass(/before:bg-warning-9/);
  });

  test("run warning/regression badges keep regression-only behavior and render both badges together", async ({
    page,
  }) => {
    const runs = await apiGet<RunListResponse>("/runs");
    const template = warningRunListItem ?? runs.items[0];
    if (!template) {
      throw new Error("RUN-845 setup failed: no run template available");
    }

    const warningOnlyRun: RunListItem = {
      ...template,
      id: "run845-warning-only",
      workflow_id: "wf_run845_warning_only",
      workflow_name: "RUN-845 warning-only",
      regression_count: 0,
      warnings: warningRunListItem?.warnings?.length
        ? warningRunListItem.warnings
        : [
            {
              message: "Injected warning-only row",
              source: "tool_governance",
              context: "warning_only",
            },
          ],
      run_number: 8451,
    };

    const regressionOnlyRun: RunListItem = {
      ...template,
      id: "run845-regression-only",
      workflow_id: "wf_run845_regression_only",
      workflow_name: "RUN-845 regression-only",
      regression_count: 4,
      warnings: [],
      run_number: 8452,
    };

    const bothBadgesRun: RunListItem = {
      ...template,
      id: "run845-both-badges",
      workflow_id: "wf_run845_both_badges",
      workflow_name: "RUN-845 both-badges",
      regression_count: 2,
      warnings: [
        {
          message: "Injected warning for both-badges row",
          source: "tool_definitions",
          context: "lookup_profile",
        },
      ],
      run_number: 8453,
    };

    await page.route("**/api/runs*", async (route) => {
      const url = new URL(route.request().url());
      if (url.pathname !== "/api/runs") {
        await route.continue();
        return;
      }

      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [warningOnlyRun, regressionOnlyRun, bothBadgesRun],
          total: 3,
          offset: 0,
          limit: 20,
        }),
      });
    });

    await page.route("**/api/runs/run845-regression-only/regressions", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ count: 4, issues: [{ type: "assertion_regression" }] }),
      });
    });

    await page.route("**/api/runs/run845-both-badges/regressions", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ count: 2, issues: [{ type: "cost_spike" }] }),
      });
    });

    await gotoShellRoute(page, "/runs");

    const warningOnlyRow = rowForWorkflow(page, "RUN-845 warning-only");
    await expect(warningOnlyRow).toBeVisible();
    await expect(warningOnlyRow.getByRole("status", { name: /warning/i })).toBeVisible();
    await expect(warningOnlyRow.locator("td").first()).not.toHaveClass(/before:bg-warning-9/);

    const regressionOnlyRow = rowForWorkflow(page, "RUN-845 regression-only");
    await expect(regressionOnlyRow).toBeVisible();
    await expect(regressionOnlyRow.getByRole("status", { name: /warning/i })).toHaveCount(0);
    await expect(regressionOnlyRow.locator('span[style*="--warning-11"]')).toBeVisible();
    await expect(regressionOnlyRow.locator("td").first()).toHaveClass(/before:bg-warning-9/);

    const bothBadgesRow = rowForWorkflow(page, "RUN-845 both-badges");
    await expect(bothBadgesRow).toBeVisible();
    await expect(bothBadgesRow.getByRole("status", { name: /warning/i })).toBeVisible();
    await expect(bothBadgesRow.locator('span[style*="--warning-11"]')).toBeVisible();
    await expect(bothBadgesRow.locator("td").first()).toHaveClass(/before:bg-warning-9/);
  });

  test("flows page WorkflowRow shows warning badge from live workflow warnings", async ({ page }) => {
    await gotoShellRoute(page, "/flows");

    const workflowRow = page.getByTestId(`workflow-row-${warningWorkflowId}`);
    await expect(workflowRow).toBeVisible();

    const warningBadge = workflowRow.getByRole("status", { name: /warning/i });
    await expect(warningBadge).toBeVisible();

    await warningBadge.hover();
    await expect(page.getByText("1 warning")).toBeVisible();
    await expect(page.getByText(/undeclared tool/i)).toBeVisible();
  });
});
