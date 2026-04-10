import { expect, type Page } from "@playwright/test";

export function workflowUrlId(url: string): string {
  const match = url.match(/\/workflows\/([^/]+)\/edit(?:\?|$)/);
  if (!match) {
    throw new Error(`Workflow edit route missing from URL: ${url}`);
  }

  return match[1];
}

export async function gotoWorkflowEditor(page: Page, workflowId: string) {
  await page.goto(`/workflows/${workflowId}/edit`);
  await expect(page).not.toHaveURL(/\/setup\/start/);
  await expect(page.getByTestId("workflow-name-display")).toBeVisible({ timeout: 15_000 });
}

export async function openCanvasTab(page: Page) {
  await page.getByTestId("workflow-tab-canvas").click();
  await expect(page.getByTestId("workflow-tab-canvas")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
}

export async function openYamlTab(page: Page) {
  await page.getByTestId("workflow-tab-yaml").click();
  await expect(page.getByTestId("workflow-yaml-editor")).toBeVisible({ timeout: 15_000 });
  await expect(page.locator(".monaco-editor")).toBeVisible({ timeout: 15_000 });
}

export async function setWorkflowYaml(page: Page, yaml: string) {
  await openYamlTab(page);
  await page.evaluate((nextYaml) => {
    type MonacoWindow = Window & {
      monaco?: {
        editor?: {
          getModels?: () => Array<{ setValue: (value: string) => void }>;
        };
      };
    };

    const model = (window as MonacoWindow).monaco?.editor?.getModels?.()?.[0];
    if (!model) {
      throw new Error("Monaco model not available");
    }
    model.setValue(nextYaml);
  }, yaml);
}

export async function readWorkflowYaml(page: Page): Promise<string> {
  await openYamlTab(page);
  return page.evaluate(() => {
    type MonacoWindow = Window & {
      monaco?: {
        editor?: {
          getModels?: () => Array<{ getValue: () => string }>;
        };
      };
    };

    const model = (window as MonacoWindow).monaco?.editor?.getModels?.()?.[0];
    if (!model) {
      throw new Error("Monaco model not available");
    }

    return model.getValue();
  });
}

export async function saveWorkflowDraft(page: Page, message = "E2E save") {
  const saveButton = page.getByTestId("workflow-save-button");
  await expect(saveButton).toBeEnabled({ timeout: 10_000 });
  await saveButton.click();

  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible({ timeout: 10_000 });
  await dialog.locator("#commit-message").fill(message);
  await dialog.getByRole("button", { name: "Save" }).click();
  await expect(dialog).not.toBeVisible({ timeout: 15_000 });
}
