import { describe, expect, it } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

const SRC_DIR = resolve(__dirname, "../../..");
const SHARED_DIR = resolve(__dirname, "..");

function readSource(relativePath: string): string {
  return readFileSync(resolve(SRC_DIR, relativePath), "utf-8");
}

function sharedFileExists(filename: string): boolean {
  return existsSync(resolve(SHARED_DIR, filename));
}

describe("RUN-511 shared dead leaf cleanup", () => {
  it("removes dead shared leaf component files from the shipped runtime tree", () => {
    expect(sharedFileExists("CrudListPage.tsx")).toBe(false);
    expect(sharedFileExists("NodeBadge.tsx")).toBe(false);
    expect(sharedFileExists("CostDisplay.tsx")).toBe(false);
  });

  it("removes stale shared barrel exports tied only to deleted shared leaves", () => {
    const source = readSource("components/shared/index.ts");

    expect(source).not.toMatch(/CrudListPage/);
    expect(source).not.toMatch(/CrudListPageConfig/);
    expect(source).not.toMatch(/NodeBadge/);
    expect(source).not.toMatch(/NodeType/);
    expect(source).not.toMatch(/CostDisplay/);
  });
});

describe("RUN-511 shared protected boundaries", () => {
  it("keeps DeleteConfirmDialog available for live workflow and provider screens", () => {
    expect(sharedFileExists("DeleteConfirmDialog.tsx")).toBe(true);

    const workflowsTab = readSource("features/flows/WorkflowsTab.tsx");
    const providersTab = readSource("features/settings/ProvidersTab.tsx");

    expect(workflowsTab).toMatch(/DeleteConfirmDialog/);
    expect(providersTab).toMatch(/DeleteConfirmDialog/);
  });

  it("keeps StatusBadge available for live runs and provider screens", () => {
    expect(sharedFileExists("StatusBadge.tsx")).toBe(true);

    const runCanvasNode = readSource("features/runs/RunCanvasNode.tsx");
    const runInspectorPanel = readSource("features/runs/RunInspectorPanel.tsx");
    const providersTab = readSource("features/settings/ProvidersTab.tsx");

    expect(runCanvasNode).toMatch(/StatusBadge/);
    expect(runInspectorPanel).toMatch(/StatusBadge/);
    expect(providersTab).toMatch(/StatusBadge/);
  });
});
