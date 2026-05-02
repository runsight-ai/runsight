import { expect, test, type Page } from "@playwright/test";

import {
  COMPLETED_RUN_ID,
  installContextAuditRoutes,
  LIVE_RUN_ID,
  LONG_REF,
} from "./helpers/context-audit-fixture";

test.describe.configure({ mode: "serial" });

test.beforeEach(({ page }) => {
  page.on("pageerror", (error) => {
    console.log(`pageerror: ${error.message}`);
  });
  page.on("console", (message) => {
    if (message.type() === "error") {
      console.log(`browser console error: ${message.text()}`);
    }
  });
});

async function openAuditTab(page: Page) {
  await expect(page.getByTestId("surface-topbar")).toBeVisible({ timeout: 15000 });
  await expect(page.getByTestId("surface-center")).toBeVisible({ timeout: 15000 });
  await page.getByTestId("workflow-audit-tab").click();
  await expect(page.getByTestId("workflow-audit-panel")).toBeVisible({ timeout: 15000 });
}

test.describe("Context audit route-mocked browser contract", () => {
  test("completed run loads historical audit records, access badges, long rows, and clean fork payload", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1366, height: 900 });
    const { contextAuditRequests, workflowCreateBodies } = await installContextAuditRoutes(page);

    await page.goto(`/runs/${COMPLETED_RUN_ID}`);
    await openAuditTab(page);

    await expect
      .poll(() => contextAuditRequests.some((path) => path.includes("page_size=100")))
      .toBe(true);

    const auditPanel = page.getByTestId("workflow-audit-panel");
    await expect(auditPanel).toContainText("declared_consumer");
    await expect(auditPanel).toContainText("secret_producer.public_summary");
    await expect(auditPanel).toContainText("strict_missing");
    await expect(auditPanel).toContainText("missing");
    await expect(auditPanel).toContainText("error");
    await expect(auditPanel).toContainText(LONG_REF);
    await expect(auditPanel).toContainText("declared_code");
    await expect(auditPanel).not.toContainText("all_access");

    await expect(page.getByTestId("node-Declared Inspector")).toContainText("Access declared");
    await expect(page.getByTestId("node-Strict Missing")).toContainText("Denied 1");
    await expect(page.locator(".react-flow__edge.context-overlay")).toHaveCount(2);

    await expectNoDocumentHorizontalOverflow(page);
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(auditPanel).toContainText(LONG_REF);
    await expect(auditPanel).toContainText("missing");
    await expect(auditPanel).toContainText("error");
    await expectNoDocumentHorizontalOverflow(page);

    await page.setViewportSize({ width: 1366, height: 900 });
    await page.getByRole("button", { name: "Fork" }).click();
    await expect
      .poll(() => workflowCreateBodies.length, { timeout: 15000 })
      .toBe(1);
    expect(JSON.stringify(workflowCreateBodies[0])).not.toContain("context-overlay");
    expect(JSON.stringify(workflowCreateBodies[0])).not.toContain("contextOverlay");
    expect(JSON.stringify(workflowCreateBodies[0])).not.toContain("access: all");
  });

  test("active run appends live context_resolution SSE and ignores malformed audit events", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 820 });
    const { contextAuditRequests } = await installContextAuditRoutes(page, { liveAudit: true });

    await page.goto(`/runs/${LIVE_RUN_ID}`);
    await openAuditTab(page);

    await expect
      .poll(() => contextAuditRequests.some((path) => path.includes(LIVE_RUN_ID)))
      .toBe(true);

    const auditPanel = page.getByTestId("workflow-audit-panel");
    await expect(auditPanel).toContainText("strict_missing", { timeout: 15000 });
    await expect(auditPanel).toContainText("denied");
    await expect(auditPanel).toContainText("error");
    await expect(auditPanel).toContainText(LONG_REF);

    const strictMissingNode = page.getByTestId("node-Strict Missing");
    await expect(strictMissingNode).toContainText("Failed");
    await expect(strictMissingNode).toContainText("Denied 1");

    await auditPanel.getByRole("button", { name: "Open context audit for strict_missing" }).click();
    const inspector = page.getByTestId("right-inspector");
    await expect(inspector).toBeVisible({ timeout: 15000 });
    await expect(inspector.getByRole("tab", { name: "Context" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await expect(inspector).toContainText("Access declared");
    await expect(inspector).toContainText("denied");
    await expect(inspector).toContainText("error");
  });
});

async function expectNoDocumentHorizontalOverflow(page: Page) {
  await expect
    .poll(async () =>
      page.evaluate(() => {
        const root = document.documentElement;
        return root.scrollWidth - root.clientWidth;
      }),
    )
    .toBeLessThanOrEqual(1);
}
