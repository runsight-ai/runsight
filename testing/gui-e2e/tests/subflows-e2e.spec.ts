import { test, expect, type Page } from "@playwright/test";

test.describe.configure({ mode: "serial" });

const API = "http://localhost:8000/api";
const TEST_PREFIX = `e2e-subflows-${Date.now()}`;

type WorkflowResponse = {
  id: string;
  name?: string | null;
  yaml?: string | null;
};

type TrackedWorkflow = {
  id: string;
  name: string | null;
};

type ProviderResponse = {
  id: string;
  is_active?: boolean;
};

type ProviderListResponse = {
  items: ProviderResponse[];
  total: number;
};

type RunSummary = {
  id: string;
  workflow_id: string;
  workflow_name?: string;
  status: string;
  created_at: number;
  parent_run_id?: string | null;
  root_run_id?: string | null;
  depth?: number;
};

type RunListResponse = {
  items: RunSummary[];
  total: number;
};

type RunNodeResponse = {
  node_id: string;
  status: string;
  output?: string | null;
  child_run_id?: string | null;
  exit_handle?: string | null;
};

async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API}${path}`);
  if (!response.ok) {
    throw new Error(`GET ${path} failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function apiPost<T>(path: string, body: unknown): Promise<T> {
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

async function apiPut<T>(path: string, body: unknown): Promise<T> {
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

async function apiDelete(path: string): Promise<void> {
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

async function ensureActiveProvider(): Promise<string | null> {
  const providers = await apiGet<ProviderListResponse>("/settings/providers");
  const hasActiveProvider = providers.items.some((provider) => provider.is_active ?? true);
  if (hasActiveProvider) {
    return null;
  }

  const id = `${TEST_PREFIX}-provider-openai`;
  const created = await apiPost<ProviderResponse>("/settings/providers", {
    id,
    kind: "provider",
    name: `${TEST_PREFIX}-provider-openai`,
  });
  return created.id;
}

async function hasActiveProvider(): Promise<boolean> {
  const providers = await apiGet<ProviderListResponse>("/settings/providers");
  return providers.items.some((provider) => provider.is_active ?? true);
}

async function createWorkflowViaUi(
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
  const trackedWorkflow: TrackedWorkflow = { id: workflowId, name: name };
  onCreated(trackedWorkflow);

  await page.goto(`/workflows/${created.id}/edit`);
  await expect(page).toHaveURL(/\/workflows\/[^/]+\/edit/, { timeout: 15000 });

  await expect.poll(async () => {
    const workflow = await apiGet<WorkflowResponse>(`/workflows/${created.id}`);
    return workflow.name ?? null;
  }).toBe(name);

  trackedWorkflow.name = name;
  return { id: created.id, name };
}

async function waitForWorkflowRun(workflowId: string, expectedStatus: "completed" | "failed") {
  await expect.poll(async () => {
    const runs = await apiGet<RunListResponse>(`/runs?workflow_id=${workflowId}&limit=10`);
    return runs.items[0]?.status ?? null;
  }, { timeout: 30000 }).toBe(expectedStatus);

  const runs = await apiGet<RunListResponse>(`/runs?workflow_id=${workflowId}&limit=10`);
  const run = runs.items[0];
  if (!run) {
    throw new Error(`No run found for workflow ${workflowId}`);
  }
  return run;
}

async function waitForChildRun(parentRunId: string, expectedStatus: "completed" | "failed") {
  await expect.poll(async () => {
    const children = await apiGet<RunSummary[]>(`/runs/${parentRunId}/children`);
    return children[0]?.status ?? null;
  }, { timeout: 30000 }).toBe(expectedStatus);

  const children = await apiGet<RunSummary[]>(`/runs/${parentRunId}/children`);
  const child = children[0];
  if (!child) {
    throw new Error(`No child run found for parent run ${parentRunId}`);
  }
  return child;
}

async function waitForRunNode(
  runId: string,
  nodeId: string,
  expectedStatus: "completed" | "failed",
) {
  await expect.poll(async () => {
    const nodes = await apiGet<RunNodeResponse[]>(`/runs/${runId}/nodes`);
    const node = nodes.find((candidate) => candidate.node_id === nodeId);
    return node?.status ?? null;
  }, { timeout: 30000 }).toBe(expectedStatus);

  const nodes = await apiGet<RunNodeResponse[]>(`/runs/${runId}/nodes`);
  const node = nodes.find((candidate) => candidate.node_id === nodeId);
  if (!node) {
    throw new Error(`No node ${nodeId} found for run ${runId}`);
  }
  return node;
}

async function expectRunDeleted(runId: string) {
  await expect
    .poll(async () => {
      const response = await fetch(`${API}/runs/${runId}`);
      return response.status;
    }, { timeout: 30000 })
    .toBe(404);
}

async function runWorkflowFromEditor(page: Page, workflowId: string) {
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

async function assertProviderGateOpensFromEditor(page: Page, workflowId: string) {
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

  await expect.poll(async () => {
    const workflowEntity = await apiGetOptional<WorkflowResponse>(`/workflows/${workflow.id}`);
    return workflowEntity === null;
  }).toBe(true);

  await expect.poll(async () => {
    const runs = await apiGet<RunListResponse>(`/runs?workflow_id=${workflow.id}&limit=20`);
    return runs.total;
  }, { timeout: 30000 }).toBe(0);
}

async function cleanupWorkflow(page: Page, workflow: TrackedWorkflow) {
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
  await expect.poll(async () => {
    const deletedWorkflow = await apiGetOptional<WorkflowResponse>(`/workflows/${workflow.id}`);
    return deletedWorkflow === null;
  }).toBe(true);

  await expect.poll(async () => {
    const runs = await apiGet<RunListResponse>(`/runs?workflow_id=${workflow.id}&limit=20`);
    return runs.total;
  }, { timeout: 30000 }).toBe(0);
}

function buildHappyChildYaml(workflowId: string, workflowName: string): string {
  return [
    'version: "1.0"',
    `id: ${workflowId}`,
    "kind: workflow",
    "interface:",
    "  inputs:",
    "    - name: topic",
    "      target: shared_memory.topic",
    "  outputs:",
    "    - name: summary",
    "      source: results.compose_summary",
    "blocks:",
    "  compose_summary:",
    "    type: code",
    "    access: all",
    "    code: |",
    "      def main(data):",
    '          topic = data["shared_memory"]["topic"]',
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

function buildFailingChildYaml(workflowId: string, workflowName: string): string {
  return [
    'version: "1.0"',
    `id: ${workflowId}`,
    "kind: workflow",
    "interface:",
    "  inputs:",
    "    - name: topic",
    "      target: shared_memory.topic",
    "  outputs: []",
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

function buildHappyParentYaml(
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
    "      results.final_summary: summary",
    "  confirm_summary:",
    "    type: code",
    "    access: all",
    "    code: |",
    "      def main(data):",
    '          return data["results"]["final_summary"]',
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

function buildFailingParentYaml(
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

test("subflows run end to end through the GUI for happy and failing paths", async ({ page }) => {
  test.setTimeout(180000);
  const createdWorkflows: TrackedWorkflow[] = [];
  let createdProviderId: string | null = null;
  const createdRunIds: string[] = [];

  try {
    await apiPut("/settings/app", { onboarding_completed: true, fallback_enabled: false });

    const happyChildName = `${TEST_PREFIX}-child-happy`;
    const failingChildName = `${TEST_PREFIX}-child-failing`;
    const happyParentName = `${TEST_PREFIX}-parent-happy`;
    const failingParentName = `${TEST_PREFIX}-parent-failing`;

    const happyChild = await createWorkflowViaUi(
      page,
      happyChildName,
      (workflowId) => buildHappyChildYaml(workflowId, happyChildName),
      (workflow) => createdWorkflows.push(workflow),
    );

    const failingChild = await createWorkflowViaUi(
      page,
      failingChildName,
      (workflowId) => buildFailingChildYaml(workflowId, failingChildName),
      (workflow) => createdWorkflows.push(workflow),
    );

    const happyParent = await createWorkflowViaUi(
      page,
      happyParentName,
      (workflowId) => buildHappyParentYaml(workflowId, happyParentName, happyChild.id),
      (workflow) => createdWorkflows.push(workflow),
    );

    const failingParent = await createWorkflowViaUi(
      page,
      failingParentName,
      (workflowId) => buildFailingParentYaml(workflowId, failingParentName, failingChild.id),
      (workflow) => createdWorkflows.push(workflow),
    );

    if (!(await hasActiveProvider())) {
      await assertProviderGateOpensFromEditor(page, happyParent.id);
      createdProviderId = await ensureActiveProvider();
    }

    await page.goto(`/workflows/${happyParent.id}/edit`);
    await page.waitForLoadState("networkidle");
    await runWorkflowFromEditor(page, happyParent.id);

    const happyParentRun = await waitForWorkflowRun(happyParent.id, "completed");
    createdRunIds.push(happyParentRun.id);
    const happyChildRun = await waitForChildRun(happyParentRun.id, "completed");
    createdRunIds.push(happyChildRun.id);
    const happyPrepareNode = await waitForRunNode(
      happyParentRun.id,
      "prepare_input",
      "completed",
    );
    const happySubflowNode = await waitForRunNode(
      happyParentRun.id,
      "call_happy_child",
      "completed",
    );
    const happyConfirmNode = await waitForRunNode(
      happyParentRun.id,
      "confirm_summary",
      "completed",
    );
    const happyChildSummaryNode = await waitForRunNode(
      happyChildRun.id,
      "compose_summary",
      "completed",
    );
    expect(happyPrepareNode.output).toBe("alpha topic");
    expect(happySubflowNode?.status).toBe("completed");
    expect(happySubflowNode?.child_run_id).toBeTruthy();
    expect(happySubflowNode?.child_run_id).toBe(happyChildRun.id);
    expect(happyConfirmNode.output).toBe("happy child handled alpha topic");
    expect(happyChildSummaryNode.output).toBe("happy child handled alpha topic");
    expect(happyChildRun.parent_run_id).toBe(happyParentRun.id);
    expect(happyChildRun.workflow_id).toBe(happyChild.id);
    expect(happyChildRun.workflow_name).toBe(happyChild.name);

    await page.goto(`/workflows/${failingParent.id}/edit`);
    await page.waitForLoadState("networkidle");
    await runWorkflowFromEditor(page, failingParent.id);

    const failingParentRun = await waitForWorkflowRun(failingParent.id, "failed");
    createdRunIds.push(failingParentRun.id);
    const failingChildRun = await waitForChildRun(failingParentRun.id, "failed");
    createdRunIds.push(failingChildRun.id);
    const failingSubflowNode = await waitForRunNode(
      failingParentRun.id,
      "call_failing_child",
      "failed",
    );
    expect(failingSubflowNode?.status).toBe("failed");
    expect(failingSubflowNode?.child_run_id).toBeTruthy();
    expect(failingSubflowNode?.child_run_id).toBe(failingChildRun.id);
    expect(failingChildRun.parent_run_id).toBe(failingParentRun.id);
    expect(failingChildRun.workflow_id).toBe(failingChild.id);
    expect(failingChildRun.workflow_name).toBe(failingChild.name);
  } finally {
    for (const workflow of [...createdWorkflows].reverse()) {
      await cleanupWorkflow(page, workflow);
    }

    for (const runId of createdRunIds) {
      await expectRunDeleted(runId);
    }

    if (createdProviderId) {
      await apiDelete(`/settings/providers/${createdProviderId}`);
    }
  }
});
