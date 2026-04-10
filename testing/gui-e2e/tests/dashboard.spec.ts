import { expect, test } from "@playwright/test";

import {
  apiDelete,
  apiGet,
  apiPost,
  gotoShellRoute,
  useShellReadyWorkspace,
} from "./helpers/shellReady";
import { workflowUrlId } from "./helpers/workflowEditor";

test.describe.configure({ mode: "serial" });
useShellReadyWorkspace(test);

type WorkflowSummary = {
  id: string;
  name: string;
};

type WorkflowListResponse = {
  items: WorkflowSummary[];
  total: number;
};

type DashboardResponse = {
  runs_today: number;
  eval_pass_rate: number | null;
  cost_today_usd: number;
  regressions: number | null;
};

test.describe("Home dashboard", () => {
  const createdWorkflowIds = new Set<string>();

  test.beforeAll(async () => {
    const workflow = await apiPost<WorkflowSummary>("/workflows", {
      yaml: "",
      canvas_state: {
        nodes: [],
        edges: [],
        viewport: { x: 0, y: 0, zoom: 1 },
        selected_node_id: null,
        canvas_mode: "dag",
      },
      commit: false,
    });
    createdWorkflowIds.add(workflow.id);
  });

  test.afterAll(async () => {
    for (const workflowId of createdWorkflowIds) {
      await apiDelete(`/workflows/${workflowId}`);
    }
  });

  test("renders the Home dashboard shell with KPI cards and the current no-runs state", async ({
    page,
  }) => {
    await gotoShellRoute(page, "/");

    await expect(page.getByRole("heading", { name: "Home" })).toBeVisible();
    await expect(page.getByRole("button", { name: "New Workflow" })).toBeVisible();
    await expect(page.getByText("Runs Today", { exact: true })).toBeVisible();
    await expect(page.getByText("Eval Pass Rate", { exact: true })).toBeVisible();
    await expect(page.getByText("Cost Today", { exact: true })).toBeVisible();
    await expect(page.getByText("Regressions", { exact: true })).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "No runs yet" }).or(
        page.getByRole("region", { name: "Items needing attention" }),
      ),
    ).toBeVisible();
  });

  test("shows dashboard KPI values from the live dashboard API", async ({ page }) => {
    const dashboard = await apiGet<DashboardResponse>("/dashboard");

    await gotoShellRoute(page, "/");

    await expect(page.getByText(String(dashboard.runs_today), { exact: true }).first()).toBeVisible();
    await expect(
      page.getByText(
        dashboard.regressions == null ? "—" : String(dashboard.regressions),
        { exact: true },
      ).first(),
    ).toBeVisible();
  });

  test("creates a workflow directly from Home without opening a modal", async ({ page }) => {
    await gotoShellRoute(page, "/");

    await page.getByRole("button", { name: "New Workflow" }).click();

    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(page).toHaveURL(/\/workflows\/[^/]+\/edit(?:\?.*)?$/, { timeout: 15_000 });

    const workflowId = workflowUrlId(page.url());
    createdWorkflowIds.add(workflowId);

    const workflows = await apiGet<WorkflowListResponse>("/workflows");
    expect(workflows.items.some((workflow) => workflow.id === workflowId)).toBe(true);
  });
});
