import { expect, test } from "@playwright/test";

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

type WorkflowResponse = {
  id: string;
  kind: "workflow";
  name?: string | null;
  warnings?: WarningItem[];
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

function warningWorkflowYaml(workflowId: string, soulId: string, workflowName: string) {
  return `version: "1.0"
id: ${workflowId}
kind: workflow
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

test.describe("Parser warnings browser smoke", () => {
  test.beforeAll(async () => {
    const suffix = Date.now().toString(36);
    warningSoulId = `parser-warning-soul-${suffix}`;
    warningWorkflowId = `parser-warning-flow-${suffix}`;
    warningWorkflowName = `Parser warning flow ${suffix}`;

    await apiPost("/souls", {
      id: warningSoulId,
      kind: "soul",
      name: "Parser Warning Soul",
      role: "Parser Warning Soul",
      system_prompt: "Parser warning soul for e2e coverage.",
      tools: ["http"],
      provider: "shell-ready-fixture-provider",
      model_name: "shell-ready-fixture-model",
    });

    const workflow = await apiPost<WorkflowResponse>("/workflows", {
      name: warningWorkflowName,
      yaml: warningWorkflowYaml(warningWorkflowId, warningSoulId, warningWorkflowName),
      canvas_state: CANVAS_STATE,
      commit: false,
    });
    warningWorkflowId = workflow.id;

    await expect
      .poll(async () => {
        const currentWorkflow = await apiGet<WorkflowResponse>(`/workflows/${warningWorkflowId}`);
        return currentWorkflow.warnings?.length ?? 0;
      })
      .toBeGreaterThan(0);
  });

  test.afterAll(async () => {
    if (warningWorkflowId) {
      await safeDelete(`/workflows/${warningWorkflowId}?force=true`);
    }
    if (warningSoulId) {
      await safeDelete(`/souls/${warningSoulId}`);
    }
  });

  test("flows page shows a warning badge and tooltip from live workflow warnings", async ({
    page,
  }) => {
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
