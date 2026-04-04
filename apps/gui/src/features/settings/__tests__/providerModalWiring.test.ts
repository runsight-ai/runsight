import { describe, expect, it } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

const SRC_DIR = resolve(__dirname, "../../..");

function readSource(relativePath: string): string {
  return readFileSync(resolve(SRC_DIR, relativePath), "utf-8");
}

function fileExists(relativePath: string): boolean {
  return existsSync(resolve(SRC_DIR, relativePath));
}

const PROVIDER_MODAL_PATH = "components/provider/ProviderModal.tsx";
const ADD_PROVIDER_DIALOG_PATH = "features/settings/AddProviderDialog.tsx";
const CANVAS_PAGE_PATH = "features/canvas/CanvasPage.tsx";
const PROVIDERS_TAB_PATH = "features/settings/ProvidersTab.tsx";

describe("ProviderModal shared wiring", () => {
  it("creates a shared ProviderModal component file", () => {
    expect(
      fileExists(PROVIDER_MODAL_PATH),
      "Expected components/provider/ProviderModal.tsx to exist",
    ).toBe(true);
  });

  it("ProviderModal exports a mode prop for settings and canvas flows", () => {
    const source = readSource(PROVIDER_MODAL_PATH);
    expect(source).toMatch(/mode\s*:\s*['"]settings-add['"]\s*\|\s*['"]settings-edit['"]\s*\|\s*['"]canvas['"]/);
  });

  it("ProviderModal reuses the existing auto-test hook", () => {
    const source = readSource(PROVIDER_MODAL_PATH);
    expect(source).toMatch(/useApiKeyAutoTest/);
  });

  it("ProviderModal reuses ConnectionFeedback", () => {
    const source = readSource(PROVIDER_MODAL_PATH);
    expect(source).toMatch(/ConnectionFeedback/);
  });
});

describe("Settings flow uses ProviderModal", () => {
  it("AddProviderDialog imports ProviderModal", () => {
    const source = readSource(ADD_PROVIDER_DIALOG_PATH);
    expect(source).toMatch(/import.*ProviderModal.*from.*components\/provider\/ProviderModal|@\/components\/provider\/ProviderModal/);
  });

  it("AddProviderDialog renders ProviderModal", () => {
    const source = readSource(ADD_PROVIDER_DIALOG_PATH);
    expect(source).toMatch(/<ProviderModal\b/);
  });

  it("ProvidersTab still renders AddProviderDialog for settings entry points", () => {
    const source = readSource(PROVIDERS_TAB_PATH);
    expect(source).toMatch(/<AddProviderDialog\b/);
  });
});

describe("Canvas flow uses ProviderModal", () => {
  it("CanvasPage imports ProviderModal instead of ApiKeyModal", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).toMatch(/import.*ProviderModal.*from.*components\/provider\/ProviderModal|@\/components\/provider\/ProviderModal/);
    expect(source).not.toMatch(/import.*ApiKeyModal.*from.*features\/setup\/ApiKeyModal|@\/features\/setup\/ApiKeyModal/);
  });

  it("CanvasPage renders ProviderModal in JSX", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).toMatch(/<ProviderModal\b/);
  });
});
