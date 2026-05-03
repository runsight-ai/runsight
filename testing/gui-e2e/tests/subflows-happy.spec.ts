import { test, expect } from "@playwright/test";
import {
  apiDelete,
  assertProviderGateOpensFromEditor,
  buildHappyChildYaml,
  buildHappyParentYaml,
  cleanupWorkflow,
  createWorkflowViaUi,
  ensureActiveProvider,
  expectRunDeleted,
  hasActiveProvider,
  primeSubflowAppSettings,
  runWorkflowFromEditor,
  type TrackedWorkflow,
  waitForChildRun,
  waitForRunNode,
  waitForWorkflowRun,
} from "./helpers/subflowFixtures";

test.describe.configure({ mode: "serial" });

const TEST_PREFIX = `e2e-subflows-happy-${Date.now()}`;

test("subflows complete from the editor and link child runs", async ({ page }) => {
  test.setTimeout(180000);
  const createdWorkflows: TrackedWorkflow[] = [];
  let createdProviderId: string | null = null;
  const createdRunIds: string[] = [];

  try {
    await primeSubflowAppSettings();

    const childName = `${TEST_PREFIX}-child`;
    const parentName = `${TEST_PREFIX}-parent`;

    const child = await createWorkflowViaUi(
      page,
      childName,
      (workflowId) => buildHappyChildYaml(workflowId, childName),
      (workflow) => createdWorkflows.push(workflow),
    );

    const parent = await createWorkflowViaUi(
      page,
      parentName,
      (workflowId) => buildHappyParentYaml(workflowId, parentName, child.id),
      (workflow) => createdWorkflows.push(workflow),
    );

    if (!(await hasActiveProvider())) {
      await assertProviderGateOpensFromEditor(page, parent.id);
      createdProviderId = await ensureActiveProvider(TEST_PREFIX);
    }

    await page.goto(`/workflows/${parent.id}/edit`);
    await page.waitForLoadState("networkidle");
    await runWorkflowFromEditor(page, parent.id);

    const parentRun = await waitForWorkflowRun(parent.id, "completed");
    createdRunIds.push(parentRun.id);
    const childRun = await waitForChildRun(parentRun.id, "completed");
    createdRunIds.push(childRun.id);
    const prepareNode = await waitForRunNode(parentRun.id, "prepare_input", "completed");
    const subflowNode = await waitForRunNode(parentRun.id, "call_happy_child", "completed");
    const confirmNode = await waitForRunNode(parentRun.id, "confirm_summary", "completed");
    const childSummaryNode = await waitForRunNode(childRun.id, "compose_summary", "completed");

    expect(prepareNode.output).toBe("alpha topic");
    expect(subflowNode.status).toBe("completed");
    expect(subflowNode.child_run_id).toBeTruthy();
    expect(subflowNode.child_run_id).toBe(childRun.id);
    expect(confirmNode.output).toBe("happy child handled alpha topic");
    expect(childSummaryNode.output).toBe("happy child handled alpha topic");
    expect(childRun.parent_run_id).toBe(parentRun.id);
    expect(childRun.workflow_id).toBe(child.id);
    expect(childRun.workflow_name).toBe(child.name);
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
