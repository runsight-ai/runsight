import { expect, type Page } from "@playwright/test";

const API = "http://localhost:8000/api";

export type WorkflowResponse = {
  id: string;
  name?: string | null;
  yaml?: string | null;
};

export type TrackedWorkflow = {
  id: string;
  name: string | null;
};

export type ProviderResponse = {
  id: string;
  is_active?: boolean;
};

export type ProviderListResponse = {
  items: ProviderResponse[];
  total: number;
};

export type RunSummary = {
  id: string;
  workflow_id: string;
  workflow_name?: string;
  status: string;
  created_at: number;
  parent_run_id?: string | null;
  root_run_id?: string | null;
  depth?: number;
};

export type RunListResponse = {
  items: RunSummary[];
  total: number;
};

export type RunNodeResponse = {
  node_id: string;
  status: string;
  output?: string | null;
  child_run_id?: string | null;
  exit_handle?: string | null;
};

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API}${path}`);
  if (!response.ok) {
    throw new Error(`GET ${path} failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`POST ${path} failed with ${response.status}: ${await response.text()}`);
  }
  return response.json() as Promise<T>;
}

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`PUT ${path} failed with ${response.status}: ${await response.text()}`);
  }
  return response.json() as Promise<T>;
}

export async function apiDelete(path: string): Promise<void> {
  const response = await fetch(`${API}${path}`, { method: "DELETE" });
  if (!response.ok && response.status !== 404) {
    throw new Error(`DELETE ${path} failed with ${response.status}`);
  }
}

async function apiGetOptional<T>(path: string): Promise<T | null> {
  const response = await fetch(`${API}${path}`);
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`GET ${path} failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function ensureActiveProvider(testPrefix: string): Promise<string | null> {
  const providers = await apiGet<ProviderListResponse>("/settings/providers");
  const hasProvider = providers.items.some((provider) => provider.is_active ?? true);
  if (hasProvider) {
    return null;
  }

  const id = `${testPrefix}-provider-fixture`;
  const created = await apiPost<ProviderResponse>("/settings/providers", {
    id,
    kind: "provider",
    name: `${testPrefix}-provider-fixture`,
  });
  return created.id;
}

export async function hasActiveProvider(): Promise<boolean> {
  const providers = await apiGet<ProviderListResponse>("/settings/providers");
  return providers.items.some((provider) => provider.is_active ?? true);
}

export async function primeSubflowAppSettings(): Promise<void> {
  await apiPut("/settings/app", { onboarding_completed: true, fallback_enabled: false });
}

export async function createWorkflowViaUi(
  page: Page,
  name: string,
  buildYaml: (workflowId: string) => string,
  onCreated: (workflow: TrackedWorkflow) => void,
): Promise<{ id: string; name: string }> {
  const workflowId = name;
  const yaml = buildYaml(workflowId);
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
  const trackedWorkflow: TrackedWorkflow = { id: workflowId, name };
  onCreated(trackedWorkflow);

  await page.goto(`/workflows/${created.id}/edit`);
  await expect(page).toHaveURL(/\/workflows\/[^/]+\/edit/, { timeout: 15000 });

  await expect
    .poll(async () => {
      const workflow = await apiGet<WorkflowResponse>(`/workflows/${created.id}`);
      return workflow.name ?? null;
    })
    .toBe(name);

  trackedWorkflow.name = name;
  return { id: created.id, name };
}

export async function waitForWorkflowRun(
  workflowId: string,
  expectedStatus: "completed" | "failed",
) {
  await expect
    .poll(
      async () => {
        const runs = await apiGet<RunListResponse>(`/runs?workflow_id=${workflowId}&limit=10`);
        return runs.items[0]?.status ?? null;
      },
      { timeout: 30000 },
    )
    .toBe(expectedStatus);

  const runs = await apiGet<RunListResponse>(`/runs?workflow_id=${workflowId}&limit=10`);
  const run = runs.items[0];
  if (!run) {
    throw new Error(`No run found for workflow ${workflowId}`);
  }
  return run;
}

export async function waitForChildRun(
  parentRunId: string,
  expectedStatus: "completed" | "failed",
) {
  await expect
    .poll(
      async () => {
        const children = await apiGet<RunSummary[]>(`/runs/${parentRunId}/children`);
        return children[0]?.status ?? null;
      },
      { timeout: 30000 },
    )
    .toBe(expectedStatus);

  const children = await apiGet<RunSummary[]>(`/runs/${parentRunId}/children`);
  const child = children[0];
  if (!child) {
    throw new Error(`No child run found for parent run ${parentRunId}`);
  }
  return child;
}

export async function waitForRunNode(
  runId: string,
  nodeId: string,
  expectedStatus: "completed" | "failed",
) {
  await expect
    .poll(
      async () => {
        const nodes = await apiGet<RunNodeResponse[]>(`/runs/${runId}/nodes`);
        const node = nodes.find((candidate) => candidate.node_id === nodeId);
        return node?.status ?? null;
      },
      { timeout: 30000 },
    )
    .toBe(expectedStatus);

  const nodes = await apiGet<RunNodeResponse[]>(`/runs/${runId}/nodes`);
  const node = nodes.find((candidate) => candidate.node_id === nodeId);
  if (!node) {
    throw new Error(`No node ${nodeId} found for run ${runId}`);
  }
  return node;
}

export async function expectRunDeleted(runId: string) {
  await expect
    .poll(async () => {
      const response = await fetch(`${API}/runs/${runId}`);
      return response.status;
    }, { timeout: 30000 })
    .toBe(404);
}

export async function runWorkflowFromEditor(page: Page, workflowId: string) {
  await page.getByTestId("workflow-tab-yaml").click();
  await expect(page.getByTestId("workflow-yaml-editor")).toBeVisible({ timeout: 10000 });
  const runSurfaceButton = page.getByTestId("workflow-run-button");
  await expect(runSurfaceButton).toBeVisible({ timeout: 10000 });
  await expect(runSurfaceButton).toBeEnabled({ timeout: 10000 });
  const run = await apiPost<RunSummary>("/runs", {
    workflow_id: workflowId,
    inputs: {},
    source: "manual",
  });
  await page.goto(`/runs/${run.id}`);
  await expect(page).toHaveURL(/\/runs\/[^/]+$/, { timeout: 15000 });
}

export async function assertProviderGateOpensFromEditor(page: Page, workflowId: string) {
  await page.goto(`/workflows/${workflowId}/edit`);
  await page.waitForLoadState("networkidle");
  await page.getByTestId("workflow-tab-yaml").click();
  const addApiKeyButton = page.getByTestId("workflow-add-api-key-button");
  await expect(addApiKeyButton).toBeVisible({ timeout: 10000 });
  await addApiKeyButton.click();
  await expect(page.getByRole("dialog", { name: "Add API Key" })).toBeVisible({
    timeout: 10000,
  });
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog", { name: "Add API Key" })).not.toBeVisible({
    timeout: 10000,
  });
}

async function deleteWorkflowViaUi(page: Page, workflow: TrackedWorkflow) {
  await page.goto("/flows");
  await expect(page.getByTestId("flows-search-workflows-input")).toBeVisible({ timeout: 10000 });

  const search = page.getByTestId("flows-search-workflows-input");
  if (workflow.name) {
    await search.fill(workflow.name);
    await page.waitForTimeout(300);
  }

  const row = page.getByTestId(`workflow-row-${workflow.id}`);
  await expect(row).toBeVisible({ timeout: 5000 });

  await page.getByTestId(`workflow-delete-${workflow.id}`).first().click();
  const dialog = page.getByTestId("delete-confirm-dialog");
  await expect(dialog).toBeVisible({ timeout: 10000 });
  await dialog.getByTestId("delete-confirm-submit-button").click();

  await expect
    .poll(async () => {
      const workflowEntity = await apiGetOptional<WorkflowResponse>(`/workflows/${workflow.id}`);
      return workflowEntity === null;
    })
    .toBe(true);

  await expect
    .poll(
      async () => {
        const runs = await apiGet<RunListResponse>(`/runs?workflow_id=${workflow.id}&limit=20`);
        return runs.total;
      },
      { timeout: 30000 },
    )
    .toBe(0);
}

export async function cleanupWorkflow(page: Page, workflow: TrackedWorkflow) {
  const workflowEntity = await apiGetOptional<WorkflowResponse>(`/workflows/${workflow.id}`);
  if (!workflowEntity) {
    return;
  }

  workflow.name = workflowEntity.name ?? workflow.name;

  if (!page.isClosed()) {
    try {
      await deleteWorkflowViaUi(page, workflow);
      return;
    } catch {
      // Fall through to API cleanup when the GUI is no longer usable.
    }
  }

  await apiDelete(`/workflows/${workflow.id}`);
  await expect
    .poll(async () => {
      const deletedWorkflow = await apiGetOptional<WorkflowResponse>(`/workflows/${workflow.id}`);
      return deletedWorkflow === null;
    })
    .toBe(true);

  await expect
    .poll(
      async () => {
        const runs = await apiGet<RunListResponse>(`/runs?workflow_id=${workflow.id}&limit=20`);
        return runs.total;
      },
      { timeout: 30000 },
    )
    .toBe(0);
}

export function buildHappyChildYaml(workflowId: string, workflowName: string): string {
  return [
    'version: "1.0"',
    `id: ${workflowId}`,
    "kind: workflow",
    "inputs:",
    "  topic:",
    "    type: string",
    "blocks:",
    "  compose_summary:",
    "    type: code",
    "    inputs:",
    "      topic:",
    "        from: workflow.topic",
    "    code: |",
    "      def main(data):",
    '          topic = data["topic"]',
    '          return f"happy child handled {topic}"',
    "workflow:",
    `  name: ${workflowName}`,
    "  entry: compose_summary",
    "  transitions:",
    "    - from: compose_summary",
    "      to: null",
    "",
  ].join("\n");
}

export function buildFailingChildYaml(workflowId: string, workflowName: string): string {
  return [
    'version: "1.0"',
    `id: ${workflowId}`,
    "kind: workflow",
    "inputs:",
    "  topic:",
    "    type: string",
    "blocks:",
    "  fail_slowly:",
    "    type: code",
    "    timeout_seconds: 1",
    "    code: |",
    "      import time",
    "      def main(data):",
    "          time.sleep(2)",
    '          return "too slow"',
    "workflow:",
    `  name: ${workflowName}`,
    "  entry: fail_slowly",
    "  transitions:",
    "    - from: fail_slowly",
    "      to: null",
    "",
  ].join("\n");
}

export function buildHappyParentYaml(
  workflowId: string,
  workflowName: string,
  childWorkflowRef: string,
): string {
  return [
    'version: "1.0"',
    `id: ${workflowId}`,
    "kind: workflow",
    "blocks:",
    "  prepare_input:",
    "    type: code",
    "    code: |",
    "      def main(data):",
    '          return "alpha topic"',
    "  call_happy_child:",
    "    type: workflow",
    `    workflow_ref: ${childWorkflowRef}`,
    "    inputs:",
    "      topic: results.prepare_input",
    "    outputs:",
    "      shared_memory.final_summary: results.compose_summary",
    "  confirm_summary:",
    "    type: code",
    "    inputs:",
    "      summary:",
    "        from: shared_memory.final_summary",
    "    code: |",
    "      def main(data):",
    '          return data["summary"]',
    "workflow:",
    `  name: ${workflowName}`,
    "  entry: prepare_input",
    "  transitions:",
    "    - from: prepare_input",
    "      to: call_happy_child",
    "    - from: call_happy_child",
    "      to: confirm_summary",
    "    - from: confirm_summary",
    "      to: null",
    "",
  ].join("\n");
}

export function buildFailingParentYaml(
  workflowId: string,
  workflowName: string,
  childWorkflowRef: string,
): string {
  return [
    'version: "1.0"',
    `id: ${workflowId}`,
    "kind: workflow",
    "blocks:",
    "  prepare_input:",
    "    type: code",
    "    code: |",
    "      def main(data):",
    '          return "beta topic"',
    "  call_failing_child:",
    "    type: workflow",
    `    workflow_ref: ${childWorkflowRef}`,
    "    inputs:",
    "      topic: results.prepare_input",
    "workflow:",
    `  name: ${workflowName}`,
    "  entry: prepare_input",
    "  transitions:",
    "    - from: prepare_input",
    "      to: call_failing_child",
    "    - from: call_failing_child",
    "      to: null",
    "",
  ].join("\n");
}
