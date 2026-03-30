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

const PROVIDERS_TAB_PATH = "features/settings/ProvidersTab.tsx";
const DELETE_DIALOG_PATH = "components/shared/DeleteConfirmDialog.tsx";

describe("Providers delete dialog wiring", () => {
  it("DeleteConfirmDialog exists", () => {
    expect(
      fileExists(DELETE_DIALOG_PATH),
      "Expected shared DeleteConfirmDialog to exist",
    ).toBe(true);
  });

  it("ProvidersTab imports DeleteConfirmDialog", () => {
    const source = readSource(PROVIDERS_TAB_PATH);
    expect(source).toMatch(
      /import.*DeleteConfirmDialog.*from.*components\/shared|@\/components\/shared/,
    );
  });

  it("ProvidersTab does not use window.confirm", () => {
    const source = readSource(PROVIDERS_TAB_PATH);
    expect(source).not.toMatch(/\bconfirm\s*\(/);
    expect(source).not.toMatch(/window\.confirm/);
  });

  it("ProvidersTab tracks the provider pending deletion", () => {
    const source = readSource(PROVIDERS_TAB_PATH);
    expect(source).toMatch(/itemToDelete/);
    expect(source).toMatch(/useState<Provider \| null>\(null\)/);
  });

  it("ProvidersTab renders DeleteConfirmDialog with provider name", () => {
    const source = readSource(PROVIDERS_TAB_PATH);
    expect(source).toMatch(/<DeleteConfirmDialog\b/);
    expect(source).toMatch(/itemName=\{itemToDelete \? itemToDelete\.name : undefined\}/);
  });

  it("confirm action deletes the selected provider id", () => {
    const source = readSource(PROVIDERS_TAB_PATH);
    expect(source).toMatch(/deleteProvider\.mutate\(itemToDelete\.id/);
  });

  it("cancel action clears the pending provider", () => {
    const source = readSource(PROVIDERS_TAB_PATH);
    expect(source).toMatch(/onClose=\{\(\) => setItemToDelete\(null\)\}/);
  });

  it("pending state is passed through to DeleteConfirmDialog", () => {
    const source = readSource(PROVIDERS_TAB_PATH);
    expect(source).toMatch(/isPending=\{deleteProvider\.isPending\}/);
  });
});
