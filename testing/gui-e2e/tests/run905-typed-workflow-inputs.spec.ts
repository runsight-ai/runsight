import { expect, test, type Locator, type Page } from "@playwright/test";

import {
  apiDelete,
  apiGet,
  apiPost,
  setupShellReadyWorkspace,
} from "./helpers/shellReady";
import { gotoWorkflowEditor, setWorkflowYaml } from "./helpers/workflowEditor";

test.describe.configure({ mode: "serial" });
setupShellReadyWorkspace(test);

const TEST_PREFIX = `run905-${Date.now()}`;

type WorkflowResponse = {
  id: string;
  name?: string | null;
  input_schema?: Record<string, WorkflowInputSchemaItem> | null;
};

type WorkflowInputSchemaItem = {
  type: "string" | "number" | "boolean" | "json" | "array";
  required?: boolean;
  default?: unknown;
  description?: string | null;
  sensitive?: boolean;
};

type WorkflowInputSnapshotEntry = {
  type?: string;
  sensitive?: boolean;
  source?: string;
  value?: unknown;
};

type RunResponse = {
  id: string;
  workflow_id: string;
  workflow_name: string;
  status: string;
  branch?: string;
  source?: string;
  commit_sha?: string | null;
  run_number?: number | null;
  workflow_inputs?: Record<string, WorkflowInputSnapshotEntry> | null;
  workflow_input_schema?: Record<string, WorkflowInputSchemaItem> | null;
};

type WorkflowSimulationResponse = {
  branch: string;
  commit_sha: string;
  input_schema: Record<string, WorkflowInputSchemaItem>;
};

type RunListResponse = {
  items: RunResponse[];
  total: number;
};

async function createWorkflow(
  id: string,
  name: string,
  yaml: string,
): Promise<WorkflowResponse> {
  const created = await apiPost<WorkflowResponse>("/workflows", {
    name,
    yaml,
    canvas_state: {
      nodes: [],
      edges: [],
      viewport: { x: 0, y: 0, zoom: 1 },
      selected_node_id: null,
      canvas_mode: "dag",
    },
    commit: true,
  });

  await expect.poll(async () => {
    const workflow = await apiGet<WorkflowResponse>(`/workflows/${created.id}`);
    return workflow.id;
  }).toBe(created.id);

  return created;
}

async function deleteWorkflowIfPresent(workflowId: string) {
  try {
    await apiDelete(`/workflows/${workflowId}`);
  } catch {
    // Cleanup is best effort; the E2E runtime is rebuilt for this spec.
  }
}

async function runWorkflowFromEditor(page: Page, workflowId: string) {
  await gotoWorkflowEditor(page, workflowId);
  await clickRunButton(page);
}

async function clickRunButton(page: Page) {
  const runButton = page.getByTestId("workflow-run-button");
  await expect(runButton).toBeVisible({ timeout: 15_000 });
  await expect(runButton).toBeEnabled({ timeout: 15_000 });
  await runButton.click();
}

function currentRunId(page: Page) {
  const match = page.url().match(/\/runs\/([^/?#]+)/);
  if (!match) {
    throw new Error(`Run detail route missing from URL: ${page.url()}`);
  }
  return match[1];
}

async function expectRunDetail(page: Page) {
  await expect(page).toHaveURL(/\/runs\/[^/]+$/, { timeout: 20_000 });
  await expect(page.getByTestId("canvas-bottom-panel")).toBeVisible({ timeout: 20_000 });
  return currentRunId(page);
}

async function expectNewRunDetail(page: Page, previousRunId: string) {
  await page.waitForURL(
    (url) => {
      const match = url.pathname.match(/^\/runs\/([^/]+)$/);
      return Boolean(match && match[1] !== previousRunId);
    },
    { timeout: 20_000 },
  );
  await expect(page.getByTestId("canvas-bottom-panel")).toBeVisible({ timeout: 20_000 });
  return currentRunId(page);
}

async function waitForRunSnapshot(
  workflowId: string,
  runId: string,
): Promise<RunResponse> {
  await expect.poll(async () => {
    const run = await apiGet<RunResponse>(`/runs/${runId}`);
    return run.workflow_id === workflowId && Boolean(run.workflow_inputs);
  }, { timeout: 20_000 }).toBe(true);

  return apiGet<RunResponse>(`/runs/${runId}`);
}

async function waitForNewestWorkflowRun(workflowId: string): Promise<RunResponse> {
  await expect.poll(async () => {
    const runs = await apiGet<RunListResponse>(`/runs?workflow_id=${workflowId}&limit=10`);
    return runs.items.length;
  }, { timeout: 20_000 }).toBeGreaterThan(0);

  const runs = await apiGet<RunListResponse>(`/runs?workflow_id=${workflowId}&limit=10`);
  return runs.items[0];
}

async function workflowRunCount(workflowId: string) {
  const runs = await apiGet<RunListResponse>(`/runs?workflow_id=${workflowId}&limit=20`);
  return runs.total;
}

async function openRunsFooter(page: Page) {
  await page.getByTestId("workflow-runs-tab").click();
  await expect(page.getByTestId("workflow-runs-panel")).toBeVisible({ timeout: 15_000 });
}

async function openFirstRunInputDetails(page: Page) {
  await openRunsFooter(page);
  const viewInputs = page.getByRole("button", { name: /View inputs for run/i }).first();
  await expect(viewInputs).toBeVisible({ timeout: 15_000 });
  await viewInputs.click();

  const details = page.getByRole("region", { name: "Run input details" });
  await expect(details).toBeVisible({ timeout: 10_000 });
  return details;
}

async function openFirstRerunModal(page: Page) {
  await openRunsFooter(page);
  const rerunButton = page.getByRole("button", { name: /Rerun run/i }).first();
  await expect(rerunButton).toBeVisible({ timeout: 15_000 });
  await rerunButton.click();

  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible({ timeout: 10_000 });
  await expect(dialog.getByRole("button", { name: "Rerun" })).toBeVisible();
  return dialog;
}

async function expectNoVisibleSecret(page: Page, secret: string) {
  await expect(page.locator("body")).not.toContainText(secret);
}

async function installClipboardCapture(page: Page) {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: async (text: string) => {
          (window as Window & { __run905CopiedText?: string }).__run905CopiedText =
            String(text);
        },
      },
    });
  });
}

async function copiedText(page: Page) {
  return page.evaluate(() => {
    return (window as Window & { __run905CopiedText?: string }).__run905CopiedText ?? "";
  });
}

async function expectInlineFieldError(
  dialog: Locator,
  label: string,
  message: string,
) {
  const input = dialog.getByLabel(label);
  await expect(input).toHaveAttribute("aria-describedby", /-error$/, {
    timeout: 10_000,
  });
  const errorId = await input.getAttribute("aria-describedby");
  expect(errorId).toBeTruthy();
  await expect(dialog.locator(`[id="${errorId}"]`)).toHaveText(message);
  await expect(input).toHaveAttribute("aria-invalid", "true");
}

async function interceptBackendConfigValidationError(page: Page, workflowId: string) {
  let intercepted = false;
  const routePattern = "**/api/runs";

  await page.route(routePattern, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const body = request.postDataJSON() as { workflow_id?: unknown } | null;

    if (
      !intercepted &&
      request.method() === "POST" &&
      url.pathname === "/api/runs" &&
      body?.workflow_id === workflowId
    ) {
      intercepted = true;
      await route.fulfill({
        status: 422,
        contentType: "application/json",
        json: {
          error: "Workflow input validation failed",
          error_code: "WORKFLOW_INPUT_VALIDATION_ERROR",
          status_code: 422,
          details: {
            kind: "workflow_input_validation",
            workflow_id: workflowId,
            fields: [
              {
                field: "config",
                code: "type_mismatch",
                message: "Input 'config' must be a json.",
                input_path: ["inputs", "config"],
                expected_type: "json",
                actual_type: "array",
              },
            ],
          },
        },
      });
      return;
    }

    await route.fallback();
  });

  return async () => {
    await page.unroute(routePattern).catch(() => undefined);
    expect(intercepted).toBe(true);
  };
}

function requiredStringWorkflowYaml(id: string, name: string) {
  return [
    'version: "1.0"',
    `id: ${id}`,
    "kind: workflow",
    "inputs:",
    "  query:",
    "    type: string",
    "    required: true",
    "blocks:",
    "  echo_query:",
    "    type: code",
    "    inputs:",
    "      query:",
    "        from: workflow.query",
    "    code: |",
    "      def main(data):",
    "          return {'query': data['query']}",
    "workflow:",
    `  name: ${name}`,
    "  entry: echo_query",
    "  transitions:",
    "    - from: echo_query",
    "      to: null",
    "",
  ].join("\n");
}

function dirtyRequiredWorkflowYaml(id: string, name: string) {
  return [
    'version: "1.0"',
    `id: ${id}`,
    "kind: workflow",
    "inputs:",
    "  dirty_query:",
    "    type: string",
    "    required: true",
    "blocks:",
    "  echo_dirty_query:",
    "    type: code",
    "    inputs:",
    "      dirty_query:",
    "        from: workflow.dirty_query",
    "    code: |",
    "      def main(data):",
    "          return {'dirty_query': data['dirty_query']}",
    "workflow:",
    `  name: ${name}`,
    "  entry: echo_dirty_query",
    "  transitions:",
    "    - from: echo_dirty_query",
    "      to: null",
    "",
  ].join("\n");
}

function noInputWorkflowYaml(id: string, name: string) {
  return [
    'version: "1.0"',
    `id: ${id}`,
    "kind: workflow",
    "blocks:",
    "  start:",
    "    type: code",
    "    code: |",
    "      def main(data):",
    "          return {'ok': True}",
    "workflow:",
    `  name: ${name}`,
    "  entry: start",
    "  transitions:",
    "    - from: start",
    "      to: null",
    "",
  ].join("\n");
}

function sensitiveWorkflowYaml(id: string, name: string) {
  return [
    'version: "1.0"',
    `id: ${id}`,
    "kind: workflow",
    "inputs:",
    "  query:",
    "    type: string",
    "    required: true",
    "  api_token:",
    "    type: string",
    "    required: true",
    "    sensitive: true",
    "  config:",
    "    type: json",
    "    required: true",
    "blocks:",
    "  echo_safe_inputs:",
    "    type: code",
    "    inputs:",
    "      query:",
    "        from: workflow.query",
    "      config:",
    "        from: workflow.config",
    "    code: |",
    "      def main(data):",
    "          return {'query': data['query'], 'limit': data['config'].get('limit')}",
    "workflow:",
    `  name: ${name}`,
    "  entry: echo_safe_inputs",
    "  transitions:",
    "    - from: echo_safe_inputs",
    "      to: null",
    "",
  ].join("\n");
}

test("required string input opens the modal, validates, stores history, and reruns with editable prefill", async ({
  page,
}) => {
  test.setTimeout(120_000);

  const workflowId = `${TEST_PREFIX}-required`;
  const workflowName = `${TEST_PREFIX} required input`;
  const firstQuery = "visible query from run 905";
  const editedQuery = "edited rerun query from run 905";

  const workflow = await createWorkflow(
    workflowId,
    workflowName,
    requiredStringWorkflowYaml(workflowId, workflowName),
  );

  try {
    await runWorkflowFromEditor(page, workflow.id);

    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible({ timeout: 10_000 });
    await expect(dialog.getByLabel("Query")).toBeVisible();

    await dialog.getByRole("button", { name: "Run" }).click();
    await expect(dialog).toBeVisible();
    await expectInlineFieldError(dialog, "Query", "This field is required.");

    await dialog.getByLabel("Query").fill(firstQuery);
    await dialog.getByRole("button", { name: "Run" }).click();

    const firstRunId = await expectRunDetail(page);
    const firstRun = await waitForRunSnapshot(workflow.id, firstRunId);
    expect(firstRun.workflow_inputs?.query?.value).toBe(firstQuery);

    const details = await openFirstRunInputDetails(page);
    await expect(details).toContainText(firstQuery);

    const rerunDialog = await openFirstRerunModal(page);
    const query = rerunDialog.getByLabel("Query");
    await expect(query).toHaveValue(firstQuery);
    await query.fill(editedQuery);
    await rerunDialog.getByRole("button", { name: "Rerun" }).click();

    const rerunId = await expectNewRunDetail(page, firstRunId);
    const rerun = await waitForRunSnapshot(workflow.id, rerunId);
    expect(rerun.workflow_inputs?.query?.value).toBe(editedQuery);
  } finally {
    await deleteWorkflowIfPresent(workflow.id);
  }
});

test("workflow with no declared inputs starts immediately without opening the inputs modal", async ({
  page,
}) => {
  test.setTimeout(90_000);

  const workflowId = `${TEST_PREFIX}-no-input`;
  const workflowName = `${TEST_PREFIX} no input`;

  const workflow = await createWorkflow(
    workflowId,
    workflowName,
    noInputWorkflowYaml(workflowId, workflowName),
  );

  try {
    await runWorkflowFromEditor(page, workflow.id);

    await expect(page.getByRole("dialog")).toHaveCount(0);
    const runId = await expectRunDetail(page);
    const run = await apiGet<RunResponse>(`/runs/${runId}`);
    expect(run.workflow_inputs ?? null).toEqual({});
  } finally {
    await deleteWorkflowIfPresent(workflow.id);
  }
});

test("dirty workflow run uses backend simulation input schema and snapshot", async ({
  page,
}) => {
  test.setTimeout(120_000);

  const workflowId = `${TEST_PREFIX}-dirty`;
  const workflowName = `${TEST_PREFIX} dirty input`;
  const backendOnlyDescription = "Backend simulation response controls this description.";
  const backendOnlyDefault = "backend returned default for modal";
  const dirtyValue = "value from backend prepared dirty schema";
  let realSimulation: WorkflowSimulationResponse | null = null;

  const workflow = await createWorkflow(
    workflowId,
    workflowName,
    noInputWorkflowYaml(workflowId, workflowName),
  );

  try {
    await gotoWorkflowEditor(page, workflow.id);
    await setWorkflowYaml(page, dirtyRequiredWorkflowYaml(workflow.id, workflowName));
    await expect(page.getByTestId("workflow-save-button")).toBeEnabled({ timeout: 10_000 });

    await page.route(`**/api/workflows/${workflow.id}/simulations`, async (route) => {
      const response = await route.fetch();
      const simulation = (await response.json()) as WorkflowSimulationResponse;
      realSimulation = simulation;

      await route.fulfill({
        response,
        json: {
          ...simulation,
          input_schema: {
            dirty_query: {
              ...simulation.input_schema.dirty_query,
              required: false,
              default: backendOnlyDefault,
              description: backendOnlyDescription,
            },
          },
        },
      });
    });

    const simulationResponsePromise = page.waitForResponse((response) => {
      return (
        response.request().method() === "POST" &&
        response.url().includes(`/api/workflows/${workflow.id}/simulations`)
      );
    });

    await clickRunButton(page);

    const simulationResponse = await simulationResponsePromise;
    expect(simulationResponse.ok()).toBe(true);
    const simulation = (await simulationResponse.json()) as WorkflowSimulationResponse;
    expect(simulation.branch).toBeTruthy();
    expect(simulation.branch).not.toBe("main");
    expect(simulation.input_schema).toEqual({
      dirty_query: {
        type: "string",
        required: false,
        default: backendOnlyDefault,
        description: backendOnlyDescription,
        sensitive: false,
      },
    });
    expect(realSimulation?.input_schema.dirty_query).toEqual({
      type: "string",
      required: true,
      default: null,
      description: null,
      sensitive: false,
    });

    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible({ timeout: 10_000 });
    const dirtyInput = dialog.getByRole("textbox", { name: /^Dirty Query\b/ });
    await expect(dirtyInput).toBeVisible();
    await expect(dirtyInput).toHaveValue(backendOnlyDefault);
    await expect(dialog.getByText(backendOnlyDescription)).toBeVisible();
    await expect(dialog.getByRole("textbox", { name: /^Query\b/ })).toHaveCount(0);

    await dirtyInput.fill(dirtyValue);
    await dialog.getByRole("button", { name: "Run" }).click();

    const runId = await expectRunDetail(page);
    const run = await waitForRunSnapshot(workflow.id, runId);
    expect(run.source).toBe("simulation");
    expect(run.branch).toBe(simulation.branch);
    expect(run.commit_sha).toBe(simulation.commit_sha);
    expect(run.workflow_inputs?.dirty_query?.value).toBe(dirtyValue);
    expect(run.workflow_inputs).not.toHaveProperty("query");
    expect(run.workflow_input_schema).toEqual(realSimulation?.input_schema);
  } finally {
    await page.unroute(`**/api/workflows/${workflow.id}/simulations`).catch(() => undefined);
    await deleteWorkflowIfPresent(workflow.id);
  }
});

test("backend validation stays in the modal and sensitive values stay hidden across history, rerun, copy, detail, and errors", async ({
  page,
}) => {
  test.setTimeout(150_000);

  await installClipboardCapture(page);

  const workflowId = `${TEST_PREFIX}-sensitive`;
  const workflowName = `${TEST_PREFIX} sensitive input`;
  const firstQuery = "safe query from sensitive run";
  const editedQuery = "edited safe rerun query";
  const firstSecret = `run905-secret-never-show-${Date.now()}`;
  const secondSecret = `run905-second-secret-${Date.now()}`;

  const workflow = await createWorkflow(
    workflowId,
    workflowName,
    sensitiveWorkflowYaml(workflowId, workflowName),
  );

  try {
    await runWorkflowFromEditor(page, workflow.id);

    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible({ timeout: 10_000 });
    await dialog.getByLabel("Query").fill(firstQuery);
    await dialog.getByLabel("Api Token").fill(firstSecret);

    await dialog.getByLabel("Config").fill("[1, 2]");
    await dialog.getByRole("button", { name: "Run" }).click();

    await expect(dialog).toBeVisible();
    await expectInlineFieldError(dialog, "Config", "Enter a valid JSON object.");
    await expect(dialog.getByLabel("Query")).not.toHaveAttribute("aria-invalid", "true");
    await expect(dialog.getByLabel("Api Token")).not.toHaveAttribute("aria-invalid", "true");
    await expectNoVisibleSecret(page, firstSecret);

    const stopBackendValidationIntercept = await interceptBackendConfigValidationError(
      page,
      workflow.id,
    );
    await dialog.getByLabel("Config").fill('{"limit": 2}');
    await dialog.getByRole("button", { name: "Run" }).click();

    await expect(dialog).toBeVisible();
    await expectInlineFieldError(dialog, "Config", "Input 'config' must be a json.");
    await expect(dialog.getByLabel("Query")).not.toHaveAttribute("aria-invalid", "true");
    await expect(dialog.getByLabel("Api Token")).not.toHaveAttribute("aria-invalid", "true");
    await expectNoVisibleSecret(page, firstSecret);
    await stopBackendValidationIntercept();

    await dialog.getByLabel("Config").fill('{"limit": 2}');
    await dialog.getByRole("button", { name: "Run" }).click();

    const firstRunId = await expectRunDetail(page);
    await expectNoVisibleSecret(page, firstSecret);

    const firstRun = await waitForRunSnapshot(workflow.id, firstRunId);
    expect(firstRun.workflow_inputs?.query?.value).toBe(firstQuery);
    expect(firstRun.workflow_inputs?.api_token?.sensitive).toBe(true);
    expect(firstRun.workflow_inputs?.api_token).not.toHaveProperty("value");

    const firstDetails = await openFirstRunInputDetails(page);
    await expect(firstDetails).toContainText(firstQuery);
    await expect(firstDetails).toContainText("Sensitive input omitted.");
    await expect(firstDetails).not.toContainText(firstSecret);
    await firstDetails.getByRole("button", { name: "Copy" }).click();

    const firstCopied = await copiedText(page);
    expect(firstCopied).toContain(firstQuery);
    expect(firstCopied).not.toContain(firstSecret);
    expect(JSON.parse(firstCopied)).not.toHaveProperty("api_token");

    const countBeforeBlankRerun = await workflowRunCount(workflow.id);
    const rerunDialog = await openFirstRerunModal(page);
    await expect(rerunDialog.getByLabel("Query")).toHaveValue(firstQuery);
    await expect(rerunDialog.getByLabel("Api Token")).toHaveValue("");
    await expectNoVisibleSecret(page, firstSecret);

    await rerunDialog.getByRole("button", { name: "Rerun" }).click();
    await expect(rerunDialog).toBeVisible();
    await expect(rerunDialog.getByText("This field is required.")).toBeVisible();
    expect(await workflowRunCount(workflow.id)).toBe(countBeforeBlankRerun);

    await rerunDialog.getByLabel("Query").fill(editedQuery);
    await rerunDialog.getByLabel("Api Token").fill(secondSecret);
    await rerunDialog.getByRole("button", { name: "Rerun" }).click();

    const rerunId = await expectNewRunDetail(page, firstRunId);
    await expectNoVisibleSecret(page, firstSecret);
    await expectNoVisibleSecret(page, secondSecret);

    const rerun = await waitForRunSnapshot(workflow.id, rerunId);
    expect(rerun.workflow_inputs?.query?.value).toBe(editedQuery);
    expect(rerun.workflow_inputs?.api_token?.sensitive).toBe(true);
    expect(rerun.workflow_inputs?.api_token).not.toHaveProperty("value");

    const newestRun = await waitForNewestWorkflowRun(workflow.id);
    expect(newestRun.id).toBe(rerunId);

    const rerunDetails = await openFirstRunInputDetails(page);
    await expect(rerunDetails).toContainText(editedQuery);
    await expect(rerunDetails).not.toContainText(firstSecret);
    await expect(rerunDetails).not.toContainText(secondSecret);
    await rerunDetails.getByRole("button", { name: "Copy" }).click();

    const rerunCopied = await copiedText(page);
    expect(rerunCopied).toContain(editedQuery);
    expect(rerunCopied).not.toContain(firstSecret);
    expect(rerunCopied).not.toContain(secondSecret);
    expect(JSON.parse(rerunCopied)).not.toHaveProperty("api_token");
  } finally {
    await deleteWorkflowIfPresent(workflow.id);
  }
});
