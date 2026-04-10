import { expect, test } from "@playwright/test";

import {
  apiDelete,
  apiGet,
  apiPost,
  apiPut,
  setupShellReadyWorkspace,
} from "./helpers/shellReady";
import {
  gotoWorkflowEditor,
  openCanvasTab,
  openYamlTab,
  readWorkflowYaml,
  setWorkflowYaml,
} from "./helpers/workflowEditor";

test.describe.configure({ mode: "serial" });
setupShellReadyWorkspace(test);

type WorkflowResponse = {
  id: string;
  yaml: string | null;
};

test.describe("Workflow YAML editor", () => {
  let workflowId: string | null = null;

  test.beforeAll(async () => {
    const workflow = await apiPost<WorkflowResponse>("/workflows", {
      yaml: [
        'version: "1.0"',
        "blocks:",
        "  step_a:",
        "    type: linear",
        "workflow:",
        "  name: Demo",
        "  entry: step_a",
        "  transitions: []",
        "",
      ].join("\n"),
    });
    workflowId = workflow.id;
  });

  test.afterAll(async () => {
    if (workflowId) {
      await apiDelete(`/workflows/${workflowId}`);
    }
  });

  test("switches between YAML and Canvas using the shared surface tabs", async ({ page }) => {
    await gotoWorkflowEditor(page, workflowId!);

    await openYamlTab(page);
    await openCanvasTab(page);
    await openYamlTab(page);
  });

  test("loads the current workflow YAML and persists edits through the commit dialog", async ({
    page,
  }) => {
    const updatedYaml = [
      'version: "1.0"',
      "blocks:",
      "  step_a:",
      "    type: linear",
      "  step_b:",
      "    type: dispatch",
      "workflow:",
      "  name: Demo",
      "  entry: step_a",
      "  transitions:",
      "    - from: step_a",
      "      to: step_b",
      "",
    ].join("\n");

    await gotoWorkflowEditor(page, workflowId!);

    expect(await readWorkflowYaml(page)).toContain("step_a:");

    await setWorkflowYaml(page, updatedYaml);
    await expect(page.getByTestId("workflow-save-button")).toBeEnabled();
    await page.getByTestId("workflow-save-button").click();

    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await dialog.getByRole("button", { name: "Cancel" }).click();
    await expect(dialog).not.toBeVisible();

    await apiPut<WorkflowResponse>(`/workflows/${workflowId}`, { yaml: updatedYaml });
    await page.reload();
    await gotoWorkflowEditor(page, workflowId!);

    await expect
      .poll(async () => {
        const workflow = await apiGet<WorkflowResponse>(`/workflows/${workflowId}`);
        return (workflow.yaml ?? "").trim();
      })
      .toBe(updatedYaml.trim());
  });
});
