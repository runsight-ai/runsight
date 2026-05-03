import { expect, test, type Page } from "@playwright/test";

import {
  apiDelete,
  apiGet,
  applyFixture,
  captureWorkspace,
  restoreWorkspace,
  type ProviderFixture,
  type WorkspaceSnapshot,
} from "./helpers/shellReady";

test.describe.configure({ mode: "serial" });

type WorkflowDetail = {
  id: string;
  name: string;
  yaml?: string | null;
};

const READY_PROVIDER: ProviderFixture = {
  id: "ready-fixture-provider",
  name: "Ready Fixture",
  type: "ready-fixture-provider",
  status: "connected",
  is_active: true,
  models: ["ready-fixture-model"],
  api_key: null,
};

let originalWorkspace: WorkspaceSnapshot | null = null;
const createdWorkflowIds = new Set<string>();

function extractWorkflowIdFromUrl(page: Page): string {
  const match = page.url().match(/\/workflows\/([^/]+)\/edit(?:\?|$)/);
  expect(match).not.toBeNull();
  return match![1];
}

async function expectEditorRoute(page: Page) {
  await expect(page).toHaveURL(/\/workflows\/[^/]+\/edit(?:\?.*)?$/, { timeout: 15_000 });
}

test.beforeAll(async () => {
  originalWorkspace = await captureWorkspace();
});

test.afterEach(async () => {
  for (const workflowId of createdWorkflowIds) {
    await apiDelete(`/workflows/${workflowId}`);
  }
  createdWorkflowIds.clear();
});

test.afterAll(async () => {
  if (originalWorkspace) {
    await restoreWorkspace(originalWorkspace);
  }
});

test.describe("Onboarding journeys", () => {
  test("first visit with no providers redirects into setup and creates the template in explore mode", async ({
    page,
  }) => {
    await applyFixture([], { onboarding_completed: false });

    await page.goto("/");

    await expect(page).toHaveURL(/\/setup\/start$/, { timeout: 10_000 });
    await expect(page.getByRole("heading", { name: "How do you want to start?" })).toBeVisible();
    await expect(page.getByRole("radio", { name: "Start with a template" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    await expect(page.getByText("Explore mode")).toBeVisible();
    await expect(page.getByText("Add an API key in Settings to run this workflow")).toBeVisible();

    await page.getByRole("button", { name: "Start Building" }).click();

    await expectEditorRoute(page);
    const workflowId = extractWorkflowIdFromUrl(page);
    createdWorkflowIds.add(workflowId);

    await expect(page.getByRole("button", { name: "Add API Key" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Run" })).toHaveCount(0);

    const workflow = await apiGet<WorkflowDetail>(`/workflows/${workflowId}`);
    expect(workflow.name).toBe("Research & Review");
    expect(workflow.yaml).toContain("quality_gate:");
    expect(workflow.yaml).toContain("draft_report:");
    expect(workflow.yaml).toContain("write_error_stub:");

    const settings = await apiGet<{ onboarding_completed?: boolean }>("/settings/app");
    expect(settings.onboarding_completed).toBe(true);
  });

  test("blank-canvas onboarding creates an untitled workflow and preserves the explore-mode run gate", async ({
    page,
  }) => {
    await applyFixture([], { onboarding_completed: false });

    await page.goto("/setup/start");

    const blankCard = page.getByRole("radio", { name: "Start with a blank canvas" });
    await blankCard.click();
    await expect(blankCard).toHaveAttribute("aria-checked", "true");

    await page.getByRole("button", { name: "Start Building" }).click();

    await expectEditorRoute(page);
    const workflowId = extractWorkflowIdFromUrl(page);
    createdWorkflowIds.add(workflowId);

    await expect(page.getByRole("button", { name: "Add API Key" })).toBeVisible();

    const workflow = await apiGet<WorkflowDetail>(`/workflows/${workflowId}`);
    expect(workflow.name).toBe("Untitled Workflow");
    expect(workflow.yaml).toContain(`id: ${workflowId}`);
    expect(workflow.yaml).toContain("kind: workflow");
  });

  test("provider-present onboarding shows ready-to-run state and redirects setup away after completion", async ({
    page,
  }) => {
    await applyFixture([READY_PROVIDER], { onboarding_completed: false });

    await page.goto("/setup/start");

    await expect(page.getByText("Ready to run").first()).toBeVisible();
    await expect(page.getByText("Explore mode")).toHaveCount(0);

    await page.getByRole("button", { name: "Start Building" }).click();

    await expectEditorRoute(page);
    const workflowId = extractWorkflowIdFromUrl(page);
    createdWorkflowIds.add(workflowId);

    await expect(page.getByRole("button", { name: "Run" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Add API Key" })).toHaveCount(0);

    await page.goto("/setup/start");
    await expect(page).toHaveURL(/\/$/, { timeout: 10_000 });
    await expect(page.getByRole("heading", { name: "Home" }).first()).toBeVisible();
  });
});
