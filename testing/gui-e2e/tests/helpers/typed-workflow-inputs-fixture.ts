import { expect, type Locator, type Page } from "@playwright/test";

import {
  apiDelete,
  apiGet,
  apiPost,
} from "./shellReady";
import { gotoWorkflowEditor } from "./workflowEditor";

export type WorkflowInputSchemaItem = {
  type: "string" | "number" | "boolean" | "json" | "array";
  required?: boolean;
  default?: unknown;
  description?: string | null;
  sensitive?: boolean;
};

export type WorkflowResponse = {
  id: string;
  name?: string | null;
  input_schema?: Record<string, WorkflowInputSchemaItem> | null;
};

export type WorkflowInputSnapshotEntry = {
  type?: string;
  sensitive?: boolean;
  source?: string;
  value?: unknown;
};

export type RunResponse = {
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

export type WorkflowSimulationResponse = {
  branch: string;
  commit_sha: string;
  input_schema: Record<string, WorkflowInputSchemaItem>;
};

type RunListResponse = {
  items: RunResponse[];
  total: number;
};

export async function createWorkflow(
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

export async function deleteWorkflowIfPresent(workflowId: string) {
  try {
    await apiDelete(`/workflows/${workflowId}`);
  } catch {
    // Cleanup is best effort; the E2E runtime is rebuilt for this spec.
  }
}

export async function runWorkflowFromEditor(page: Page, workflowId: string) {
  await gotoWorkflowEditor(page, workflowId);
  await clickRunButton(page);
}

export async function clickRunButton(page: Page) {
  const runButton = page.getByTestId("workflow-run-button");
  await expect(runButton).toBeVisible({ timeout: 15_000 });
  await expect(runButton).toBeEnabled({ timeout: 15_000 });
  await runButton.click();
}

export function currentRunId(page: Page) {
  const match = page.url().match(/\/runs\/([^/?#]+)/);
  if (!match) {
    throw new Error(`Run detail route missing from URL: ${page.url()}`);
  }
  return match[1];
}

export async function expectRunDetail(page: Page) {
  await expect(page).toHaveURL(/\/runs\/[^/]+$/, { timeout: 20_000 });
  await expect(page.getByTestId("canvas-bottom-panel")).toBeVisible({ timeout: 20_000 });
  return currentRunId(page);
}

export async function expectNewRunDetail(page: Page, previousRunId: string) {
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

export async function waitForRunSnapshot(
  workflowId: string,
  runId: string,
): Promise<RunResponse> {
  await expect.poll(async () => {
    const run = await apiGet<RunResponse>(`/runs/${runId}`);
    return run.workflow_id === workflowId && Boolean(run.workflow_inputs);
  }, { timeout: 20_000 }).toBe(true);

  return apiGet<RunResponse>(`/runs/${runId}`);
}

export async function waitForNewestWorkflowRun(workflowId: string): Promise<RunResponse> {
  await expect.poll(async () => {
    const runs = await apiGet<RunListResponse>(`/runs?workflow_id=${workflowId}&limit=10`);
    return runs.items.length;
  }, { timeout: 20_000 }).toBeGreaterThan(0);

  const runs = await apiGet<RunListResponse>(`/runs?workflow_id=${workflowId}&limit=10`);
  return runs.items[0];
}

export async function workflowRunCount(workflowId: string) {
  const runs = await apiGet<RunListResponse>(`/runs?workflow_id=${workflowId}&limit=20`);
  return runs.total;
}

export async function openRunsFooter(page: Page) {
  await page.getByTestId("workflow-runs-tab").click();
  await expect(page.getByTestId("workflow-runs-panel")).toBeVisible({ timeout: 15_000 });
}

export async function openFirstRunInputDetails(page: Page) {
  await openRunsFooter(page);
  const viewInputs = page.getByRole("button", { name: /View inputs for run/i }).first();
  await expect(viewInputs).toBeVisible({ timeout: 15_000 });
  await viewInputs.click();

  const details = page.getByRole("region", { name: "Run input details" });
  await expect(details).toBeVisible({ timeout: 10_000 });
  return details;
}

export async function openFirstRerunModal(page: Page) {
  await openRunsFooter(page);
  const rerunButton = page.getByRole("button", { name: /Rerun run/i }).first();
  await expect(rerunButton).toBeVisible({ timeout: 15_000 });
  await rerunButton.click();

  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible({ timeout: 10_000 });
  await expect(dialog.getByRole("button", { name: "Rerun" })).toBeVisible();
  return dialog;
}

export async function expectNoVisibleSecret(page: Page, secret: string) {
  await expect(page.locator("body")).not.toContainText(secret);
}

export async function installClipboardCapture(page: Page) {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: async (text: string) => {
          (window as Window & { __typedInputsCopiedText?: string }).__typedInputsCopiedText =
            String(text);
        },
      },
    });
  });
}

export async function copiedText(page: Page) {
  return page.evaluate(() => {
    return (window as Window & { __typedInputsCopiedText?: string }).__typedInputsCopiedText ?? "";
  });
}

export async function expectInlineFieldError(
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

export async function interceptBackendConfigValidationError(page: Page, workflowId: string) {
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

export function requiredStringWorkflowYaml(id: string, name: string) {
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

export function dirtyRequiredWorkflowYaml(id: string, name: string) {
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

export function noInputWorkflowYaml(id: string, name: string) {
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

export function sensitiveWorkflowYaml(id: string, name: string) {
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
