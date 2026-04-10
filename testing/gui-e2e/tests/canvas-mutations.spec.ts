import { expect, test } from "@playwright/test";
import {
  apiDelete,
  apiGet,
  apiPost,
  useShellReadyWorkspace,
} from "./helpers/shellReady";
import { gotoWorkflowEditor, readWorkflowYaml } from "./helpers/workflowEditor";

test.describe.configure({ mode: "serial" });
useShellReadyWorkspace(test);

type WorkflowRecord = {
  id: string;
  name: string;
};

test.describe("Workflow name mutations", () => {
  const testWorkflowName = `e2e-mutations-${Date.now()}`;
  let createdWorkflowId: string;

  test.beforeAll(async () => {
    const created = await apiPost<WorkflowRecord>("/workflows", {
      name: testWorkflowName,
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
    createdWorkflowId = created.id;
  });

  test.afterAll(async () => {
    await apiDelete(`/workflows/${createdWorkflowId}`);
  });

  test("surface topbar shows the real workflow name", async ({ page }) => {
    await gotoWorkflowEditor(page, createdWorkflowId);
    const data = await apiGet<WorkflowRecord>(`/workflows/${createdWorkflowId}`);
    const currentName = data.name ?? "Untitled Workflow";

    await expect(page.getByTestId("workflow-name-display")).toHaveText(currentName);
    expect(currentName).toBe(data.name ?? "Untitled Workflow");
  });

  test("clicking the displayed name opens inline editing", async ({ page }) => {
    await gotoWorkflowEditor(page, createdWorkflowId);
    const currentName =
      (await apiGet<WorkflowRecord>(`/workflows/${createdWorkflowId}`)).name
      ?? "Untitled Workflow";

    await page.getByTestId("workflow-name-display").click();
    const input = page.getByTestId("workflow-name-input");

    await expect(input).toBeVisible();
    await expect(input).toHaveValue(currentName);
  });

  test("blurring a renamed workflow persists it to the API", async ({ page }) => {
    await gotoWorkflowEditor(page, createdWorkflowId);

    await page.getByTestId("workflow-name-display").click();
    const input = page.getByTestId("workflow-name-input");
    await input.clear();
    await input.pressSequentially("Updated Workflow Name");
    await expect(input).toHaveValue("Updated Workflow Name");
    await page.getByTestId("workflow-tab-canvas").click();

    await expect
      .poll(async () => (await apiGet<WorkflowRecord>(`/workflows/${createdWorkflowId}`)).name)
      .toBe("Updated Workflow Name");
    await expect(page.getByTestId("workflow-name-display")).toHaveText("Updated Workflow Name");
  });

  test("pressing Enter saves the renamed workflow", async ({ page }) => {
    await gotoWorkflowEditor(page, createdWorkflowId);

    await page.getByTestId("workflow-name-display").click();
    const input = page.getByTestId("workflow-name-input");
    await input.fill("Saved Via Enter");
    await input.press("Enter");

    await expect(page.getByTestId("workflow-name-display")).toHaveText("Saved Via Enter");
    await expect
      .poll(async () => (await apiGet<WorkflowRecord>(`/workflows/${createdWorkflowId}`)).name)
      .toBe("Saved Via Enter");
  });

  test("saving a renamed workflow also updates workflow.name in YAML", async ({ page }) => {
    await gotoWorkflowEditor(page, createdWorkflowId);

    await page.getByTestId("workflow-name-display").click();
    const input = page.getByTestId("workflow-name-input");
    await input.fill("Saved Into YAML");
    await input.press("Enter");

    await expect(page.getByTestId("workflow-name-display")).toHaveText("Saved Into YAML");
    await expect
      .poll(async () => (await apiGet<WorkflowRecord>(`/workflows/${createdWorkflowId}`)).name)
      .toBe("Saved Into YAML");
    expect(await readWorkflowYaml(page)).toContain("name: Saved Into YAML");
  });
});
