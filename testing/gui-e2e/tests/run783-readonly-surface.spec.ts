import { test, expect, type APIRequestContext, type Page } from "@playwright/test";
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { resolve, dirname } from "node:path";

test.describe.configure({ mode: "serial" });

const API = "http://127.0.0.1:8000/api";
const SEEDED_RUN_ID = "seed_rr_regression";
const SEEDED_WORKFLOW_ID = "research-review";
const forkedWorkflowIds = new Set<string>();
const CANVAS_SIDECAR_PATH = resolve(
  process.cwd(),
  "../../custom/workflows/.canvas/research-review.canvas.json",
);

type RunSummary = {
  id: string;
  workflow_id: string;
  workflow_name: string;
  status: string;
  commit_sha: string;
  total_cost_usd: number | null;
  regression_count?: number | null;
  run_number?: number | null;
};

type RunListResponse = {
  items: RunSummary[];
};

type WorkflowResponse = {
  id: string;
  name: string | null;
  description: string | null;
  yaml: string;
  canvas_state?: Record<string, unknown> | null;
};

async function apiGet<T>(request: APIRequestContext, path: string): Promise<T> {
  const response = await request.get(`${API}${path}`);
  expect(response.ok(), `GET ${path} failed with ${response.status()}`).toBeTruthy();
  return (await response.json()) as T;
}

async function apiDelete(request: APIRequestContext, path: string) {
  const response = await request.delete(`${API}${path}`);
  expect(
    [200, 404].includes(response.status()),
    `DELETE ${path} failed with ${response.status()}`,
  ).toBeTruthy();
}

async function expectSurfaceShell(page: Page) {
  await expect(page.getByTestId("surface-topbar")).toBeVisible({ timeout: 15000 });
  await expect(page.getByTestId("surface-center")).toBeVisible({ timeout: 15000 });
  await expect(page.getByTestId("surface-bottom-panel")).toBeVisible({ timeout: 15000 });
  await expect(page.getByTestId("surface-status-bar")).toBeVisible({ timeout: 15000 });
}

async function expectEditControls(page: Page) {
  await expect(page.getByTestId("workflow-save-button")).toBeVisible({ timeout: 15000 });
  await expect(
    page.locator('[data-testid="workflow-run-button"], [data-testid="workflow-add-api-key-button"]'),
  ).toBeVisible({ timeout: 15000 });
}

async function readVisibleYaml(page: Page) {
  const editor = page.getByTestId("workflow-yaml-editor");
  await expect(editor).toBeVisible({ timeout: 15000 });
  await expect(editor.locator(".monaco-editor")).toBeVisible({ timeout: 15000 });

  await expect
    .poll(async () => {
      return await page.evaluate(() => {
        type MonacoModel = { getValue?: () => string };
        type MonacoWindow = Window & {
          monaco?: {
            editor?: {
              getModels?: () => MonacoModel[];
            };
          };
        };

        const model = (window as MonacoWindow).monaco?.editor?.getModels?.()?.[0];
        return typeof model?.getValue === "function" ? model.getValue() : null;
      });
    }, { timeout: 15000 })
    .not.toBeNull();

  return await page.evaluate(() => {
    type MonacoModel = { getValue?: () => string };
    type MonacoWindow = Window & {
      monaco?: {
        editor?: {
          getModels?: () => MonacoModel[];
        };
      };
    };

    const model = (window as MonacoWindow).monaco?.editor?.getModels?.()?.[0];
    if (!model || typeof model.getValue !== "function") {
      throw new Error("Monaco model not available");
    }
    return model.getValue();
  });
}

function workflowIdFromUrl(url: string) {
  const match = url.match(/\/workflows\/([^/]+)\/edit$/);
  if (!match) {
    throw new Error(`Could not parse workflow id from ${url}`);
  }
  return decodeURIComponent(match[1]);
}

test.afterAll(async ({ request }) => {
  for (const workflowId of forkedWorkflowIds) {
    await apiDelete(request, `/workflows/${workflowId}`);
  }
});

test.describe("RUN-783 readonly surface browser flows", () => {
  test("runs page row opens the shared readonly surface and supports canvas, yaml, inspector, regressions, and fork", async ({
    page,
    request,
  }) => {
    const run = await apiGet<RunSummary>(request, `/runs/${SEEDED_RUN_ID}`);
    const runList = await apiGet<RunListResponse>(request, "/runs");
    const listRow = runList.items.find((item) => item.id === SEEDED_RUN_ID);
    expect(listRow, `Expected ${SEEDED_RUN_ID} in /api/runs`).toBeDefined();

    await page.goto("/runs");
    await expect(page.getByRole("heading", { name: "Runs" })).toBeVisible({ timeout: 15000 });

    const historicalYamlPromise = page.waitForResponse((response) => {
      return (
        response.url().includes("/api/git/file") &&
        response.url().includes(`ref=${encodeURIComponent(run.commit_sha)}`) &&
        response.status() === 200
      );
    });

    const row = page
      .locator("tbody tr")
      .filter({ hasText: run.workflow_name })
      .filter({ hasText: `#${listRow?.run_number ?? ""}` });

    await expect(row).toHaveCount(1);
    await row.click();

    await expect(page).toHaveURL(new RegExp(`/runs/${SEEDED_RUN_ID}$`), { timeout: 15000 });
    await expectSurfaceShell(page);
    await expect(page.getByText("Read-only review")).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole("button", { name: "Fork" })).toBeVisible({ timeout: 15000 });
    await expect(page.getByText("8 regressions found")).toBeVisible({ timeout: 15000 });
    await page.getByRole("button", { name: "Dismiss banner" }).click();
    await expect(page.getByText("8 regressions found")).toHaveCount(0);

    await page.getByTestId("workflow-tab-yaml").click();
    const historicalYamlResponse = await historicalYamlPromise;
    const historicalYaml = ((await historicalYamlResponse.json()) as { content: string }).content;
    const visibleYaml = await readVisibleYaml(page);
    expect(visibleYaml).toContain("slack_notifier");
    expect(visibleYaml).toBe(historicalYaml);

    await page.getByTestId("workflow-tab-canvas").click();
    const researchNode = page
      .getByTestId("surface-center")
      .locator('[role="application"] [role="group"]')
      .filter({ hasText: "Research" })
      .first();
    await expect(researchNode).toBeVisible({ timeout: 15000 });
    await researchNode.dispatchEvent("click");

    const inspector = page.getByTestId("right-inspector");
    await expect(inspector).toBeVisible({ timeout: 15000 });
    await expect(inspector.getByRole("tab", { name: "Execution" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await expect(inspector).toContainText("Research");
    await expect(inspector).toContainText("Completed");

    await page.getByTestId("workflow-tab-yaml").click();
    await expect(page.getByTestId("workflow-yaml-editor")).toBeVisible({ timeout: 15000 });

    await page.getByTestId("workflow-tab-canvas").click();
    await expect(researchNode).toBeVisible({ timeout: 15000 });

    await page.getByRole("button", { name: "Fork" }).click();
    await expect(page).toHaveURL(/\/workflows\/[^/]+\/edit$/, { timeout: 15000 });

    const forkedWorkflowId = workflowIdFromUrl(page.url());
    forkedWorkflowIds.add(forkedWorkflowId);

    await expectSurfaceShell(page);
    await expectEditControls(page);
    await expect(page.getByText("Read-only review")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Fork" })).toHaveCount(0);
    await expect(page.getByText(/regressions found/i)).toHaveCount(0);
  });

  test("direct edit route exposes the shared shell and no readonly banner state", async ({ page }) => {
    await page.goto(`/workflows/${SEEDED_WORKFLOW_ID}/edit`);

    await expectSurfaceShell(page);
    await expectEditControls(page);
    await expect(page.getByText("Read-only review")).toHaveCount(0);
    await expect(page.getByText(/regressions found/i)).toHaveCount(0);
  });

  test("missing readonly run shows a not found state", async ({ page }) => {
    await page.goto("/runs/nonexistent");

    await expect(page.getByText("Run not found")).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole("link", { name: "Back to runs" })).toBeVisible({
      timeout: 15000,
    });
  });

  test("readonly mode lays out canvas from YAML when canvas_state is missing and YAML stays accessible", async ({
    page,
    request,
  }) => {
    const originalCanvasState = existsSync(CANVAS_SIDECAR_PATH)
      ? readFileSync(CANVAS_SIDECAR_PATH, "utf-8")
      : null;

    try {
      if (existsSync(CANVAS_SIDECAR_PATH)) {
        rmSync(CANVAS_SIDECAR_PATH);
      }

      await expect
        .poll(async () => {
          const workflow = await apiGet<WorkflowResponse>(request, `/workflows/${SEEDED_WORKFLOW_ID}`);
          return workflow.canvas_state ?? null;
        }, { timeout: 15000 })
        .toBeNull();

      const run = await apiGet<RunSummary>(request, `/runs/${SEEDED_RUN_ID}`);
      const historicalYamlPromise = page.waitForResponse((response) => {
        return (
          response.url().includes("/api/git/file") &&
          response.url().includes(`ref=${encodeURIComponent(run.commit_sha)}`) &&
          response.status() === 200
        );
      });

      await page.goto(`/runs/${SEEDED_RUN_ID}`);

      await expectSurfaceShell(page);
      await page.getByTestId("workflow-tab-canvas").click();
      const researchNode = page
        .getByTestId("surface-center")
        .locator('[role="application"] [role="group"]')
        .filter({ hasText: "Research" })
        .first();
      await expect(researchNode).toBeVisible({ timeout: 15000 });
      await expect(
        page.getByText("Canvas layout unavailable", { exact: true }),
      ).toHaveCount(0);

      await page.getByTestId("workflow-tab-yaml").click();
      const historicalYamlResponse = await historicalYamlPromise;
      const historicalYaml = ((await historicalYamlResponse.json()) as { content: string }).content;
      const visibleYaml = await readVisibleYaml(page);
      expect(visibleYaml).toBe(historicalYaml);
    } finally {
      if (originalCanvasState != null) {
        mkdirSync(dirname(CANVAS_SIDECAR_PATH), { recursive: true });
        writeFileSync(CANVAS_SIDECAR_PATH, originalCanvasState);
      }

      await expect
        .poll(async () => {
          const workflow = await apiGet<WorkflowResponse>(request, `/workflows/${SEEDED_WORKFLOW_ID}`);
          return workflow.canvas_state ? "restored" : null;
        }, { timeout: 15000 })
        .toBe("restored");
    }
  });
});
