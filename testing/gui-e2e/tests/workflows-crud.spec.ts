import { expect, test } from "@playwright/test";

import {
  apiDelete,
  apiGet,
  apiPost,
  buildBlankWorkflowYaml,
  gotoShellRoute,
  setupShellReadyWorkspace,
} from "./helpers/shellReady";
import { workflowUrlId } from "./helpers/workflowEditor";

test.describe.configure({ mode: "serial" });
setupShellReadyWorkspace(test);

type WorkflowSummary = {
  id: string;
  name: string;
};

type WorkflowListResponse = {
  items: WorkflowSummary[];
  total: number;
};

test.describe("Flows CRUD", () => {
  let deleteTargetId: string | null = null;
  const createdWorkflowIds = new Set<string>();

  test.beforeAll(async () => {
    const workflowId = `e2e-flows-crud-${Date.now()}`;
    const workflow = await apiPost<WorkflowSummary>("/workflows", {
      name: "Flows CRUD",
      yaml: buildBlankWorkflowYaml(workflowId, "Flows CRUD"),
      canvas_state: {
        nodes: [],
        edges: [],
        viewport: { x: 0, y: 0, zoom: 1 },
        selected_node_id: null,
        canvas_mode: "dag",
      },
      commit: false,
    });
    deleteTargetId = workflow.id;
    createdWorkflowIds.add(workflow.id);
  });

  test.afterAll(async () => {
    for (const workflowId of createdWorkflowIds) {
      await apiDelete(`/workflows/${workflowId}`);
    }
  });

  test("loads the canonical /flows route with the current page shell", async ({ page }) => {
    await gotoShellRoute(page, "/flows");

    await expect(page.getByRole("heading", { name: "Flows" })).toBeVisible();
    await expect(page.getByTestId("flows-create-workflow-button")).toBeVisible();
    await expect(page.getByTestId("flows-search-workflows-input")).toBeVisible();
  });

  test("creates a workflow directly from Flows and lands on the edit route", async ({ page }) => {
    await gotoShellRoute(page, "/flows");

    await page.getByTestId("flows-create-workflow-button").click();

    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(page).toHaveURL(/\/workflows\/[^/]+\/edit(?:\?.*)?$/, { timeout: 15_000 });

    const workflowId = workflowUrlId(page.url());
    createdWorkflowIds.add(workflowId);

    const workflows = await apiGet<WorkflowListResponse>("/workflows");
    expect(workflows.items.some((workflow) => workflow.id === workflowId)).toBe(true);
  });

  test("deletes a workflow from the Flows list through the confirm dialog", async ({ page }) => {
    expect(deleteTargetId).not.toBeNull();

    await gotoShellRoute(page, "/flows");

    await expect(page.getByTestId(`workflow-row-${deleteTargetId}`)).toBeVisible();
    await page.getByTestId(`workflow-delete-${deleteTargetId}`).click();

    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await dialog.getByRole("button", { name: "Delete" }).click();
    await expect(dialog).not.toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId(`workflow-row-${deleteTargetId}`)).toHaveCount(0);

    const workflows = await apiGet<WorkflowListResponse>("/workflows");
    expect(workflows.items.some((workflow) => workflow.id === deleteTargetId)).toBe(false);

    createdWorkflowIds.delete(deleteTargetId!);
    deleteTargetId = null;
  });
});
