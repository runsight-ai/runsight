import { expect, test } from "@playwright/test";
import { parse } from "yaml";
import {
  apiDelete,
  apiGet,
  apiPost,
  apiPut,
  buildBlankWorkflowYaml,
  setupShellReadyWorkspace,
} from "./helpers/shellReady";
import {
  gotoWorkflowEditor,
  openCanvasTab,
  readWorkflowYaml,
  setWorkflowYaml,
} from "./helpers/workflowEditor";

test.describe.configure({ mode: "serial" });
setupShellReadyWorkspace(test);

type WorkflowRecord = {
  id: string;
  yaml?: string;
};

test.describe("Surface YAML stateful round-trip", () => {
  let workflowId: string;

  test.beforeAll(async () => {
    workflowId = `e2e-stateful-${Date.now()}`;
    const created = await apiPost<WorkflowRecord>("/workflows", {
      name: `e2e-stateful-${Date.now()}`,
      yaml: buildBlankWorkflowYaml(workflowId, "Stateful Test"),
      canvas_state: {
        nodes: [],
        edges: [],
        viewport: { x: 0, y: 0, zoom: 1 },
        selected_node_id: null,
        canvas_mode: "dag",
      },
      commit: false,
    });
    workflowId = created.id;
  });

  test.afterAll(async () => {
    await apiDelete(`/workflows/${workflowId}`);
  });

  test("preserves stateful: true after YAML save and editor reload", async ({ page }) => {
    const yamlInput = [
      'version: "1.0"',
      `id: ${workflowId}`,
      "kind: workflow",
      "blocks:",
      "  step_a:",
      "    type: code",
      "    stateful: true",
      "    code: |",
      "      def main(data):",
      "          return {'ok': True}",
      "workflow:",
      "  name: StatefulTest",
      "  entry: step_a",
      "  transitions:",
      "    - from: step_a",
      "      to: null",
      "",
    ].join("\n");

    await gotoWorkflowEditor(page, workflowId);
    await setWorkflowYaml(page, yamlInput);
    await expect(page.getByTestId("workflow-save-button")).toBeEnabled();
    await apiPut<WorkflowRecord>(`/workflows/${workflowId}`, { yaml: yamlInput });

    const saved = await apiGet<WorkflowRecord>(`/workflows/${workflowId}`);
    const persistedYaml = saved.yaml ?? "";
    expect(parse(persistedYaml).blocks.step_a.stateful).toBe(true);

    await page.reload();
    await gotoWorkflowEditor(page, workflowId);
    await openCanvasTab(page);

    await expect
      .poll(async () => {
        const reloadedYaml = await readWorkflowYaml(page);
        return parse(reloadedYaml)?.blocks?.step_a?.stateful;
      })
      .toBe(true);
  });

});
