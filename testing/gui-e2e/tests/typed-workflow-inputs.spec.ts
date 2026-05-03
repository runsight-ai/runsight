import { expect, test } from "@playwright/test";

import {
  copiedText,
  createWorkflow,
  deleteWorkflowIfPresent,
  expectInlineFieldError,
  expectNoVisibleSecret,
  expectRunDetail,
  installClipboardCapture,
  openFirstRunInputDetails,
  runWorkflowFromEditor,
  sensitiveWorkflowYaml,
  waitForRunSnapshot,
} from "./helpers/typed-workflow-inputs-fixture";
import { setupShellReadyWorkspace } from "./helpers/shellReady";

test.describe.configure({ mode: "serial" });
setupShellReadyWorkspace(test);

const TEST_PREFIX = `typed-inputs-${Date.now()}`;

test.describe("Typed workflow inputs browser smoke", () => {
  test("validates typed inputs and hides sensitive values in run history", async ({
    page,
  }) => {
    test.setTimeout(120_000);

    await installClipboardCapture(page);

    const workflowId = `${TEST_PREFIX}-sensitive`;
    const workflowName = `${TEST_PREFIX} sensitive input`;
    const queryValue = "safe query from sensitive run";
    const secretValue = `typed-inputs-secret-never-show-${Date.now()}`;

    const workflow = await createWorkflow(
      workflowId,
      workflowName,
      sensitiveWorkflowYaml(workflowId, workflowName),
    );

    try {
      await runWorkflowFromEditor(page, workflow.id);

      const dialog = page.getByRole("dialog");
      await expect(dialog).toBeVisible({ timeout: 10_000 });
      await dialog.getByLabel("Query").fill(queryValue);
      await dialog.getByLabel("Api Token").fill(secretValue);

      await dialog.getByLabel("Config").fill("[1, 2]");
      await dialog.getByRole("button", { name: "Run" }).click();

      await expect(dialog).toBeVisible();
      await expectInlineFieldError(dialog, "Config", "Enter a valid JSON object.");
      await expectNoVisibleSecret(page, secretValue);

      await dialog.getByLabel("Config").fill('{"limit": 2}');
      await dialog.getByRole("button", { name: "Run" }).click();

      const runId = await expectRunDetail(page);
      await expectNoVisibleSecret(page, secretValue);

      const run = await waitForRunSnapshot(workflow.id, runId);
      expect(run.workflow_inputs?.query?.value).toBe(queryValue);
      expect(run.workflow_inputs?.api_token?.sensitive).toBe(true);
      expect(run.workflow_inputs?.api_token).not.toHaveProperty("value");

      const details = await openFirstRunInputDetails(page);
      await expect(details).toContainText(queryValue);
      await expect(details).toContainText("Sensitive input omitted.");
      await expect(details).not.toContainText(secretValue);
      await details.getByRole("button", { name: "Copy" }).click();

      const copied = await copiedText(page);
      expect(copied).toContain(queryValue);
      expect(copied).not.toContain(secretValue);
      expect(JSON.parse(copied)).not.toHaveProperty("api_token");
    } finally {
      await deleteWorkflowIfPresent(workflow.id);
    }
  });
});
