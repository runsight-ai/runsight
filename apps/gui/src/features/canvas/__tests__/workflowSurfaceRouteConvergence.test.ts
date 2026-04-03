import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const GUI_SRC_ROOT = resolve(import.meta.dirname, "../../..");

function readSource(relativePath: string) {
  return readFileSync(resolve(GUI_SRC_ROOT, relativePath), "utf8");
}

function fileExists(relativePath: string) {
  return existsSync(resolve(GUI_SRC_ROOT, relativePath));
}

describe("RUN-596 workflow surface route convergence", () => {
  it("stops routing /workflows/:id/edit and /runs/:id through the legacy CanvasPage and RunDetail page products", () => {
    const routesSource = readSource("routes/index.tsx");

    expect(routesSource).toMatch(/path:\s*["']workflows\/:id\/edit["']/);
    expect(routesSource).toMatch(/path:\s*["']runs\/:id["']/);
    expect(routesSource).not.toMatch(/features\/canvas\/CanvasPage/);
    expect(routesSource).not.toMatch(/features\/runs\/RunDetail/);
  });

  it("reduces CanvasPage to a non-owning helper if it still exists instead of letting it keep the workflow page architecture alive", () => {
    if (!fileExists("features/canvas/CanvasPage.tsx")) {
      expect(true).toBe(true);
      return;
    }

    const source = readSource("features/canvas/CanvasPage.tsx");

    expect(source).not.toMatch(/PaletteSidebar/);
    expect(source).not.toMatch(/YamlEditor/);
    expect(source).not.toMatch(/WorkflowCanvas/);
    expect(source).not.toMatch(/CanvasBottomPanel/);
    expect(source).not.toMatch(/CanvasStatusBar/);
    expect(source).not.toMatch(/ProviderModal/);
    expect(source).not.toMatch(/CommitDialog/);
    expect(source).not.toMatch(/useCanvasStore/);
    expect(source).not.toMatch(/useWorkflowRegressions/);
    expect(source).not.toMatch(/useCreateRun/);
  });

  it("reduces RunDetail to a non-owning helper if it still exists instead of keeping a parallel historical page surface", () => {
    if (!fileExists("features/runs/RunDetail.tsx")) {
      expect(true).toBe(true);
      return;
    }

    const source = readSource("features/runs/RunDetail.tsx");

    expect(source).not.toMatch(/ReactFlow/);
    expect(source).not.toMatch(/useNodesState/);
    expect(source).not.toMatch(/useEdgesState/);
    expect(source).not.toMatch(/useRunNodes/);
    expect(source).not.toMatch(/useRunLogs/);
    expect(source).not.toMatch(/useRunRegressions/);
    expect(source).not.toMatch(/RunInspectorPanel/);
    expect(source).not.toMatch(/RunBottomPanel/);
    expect(source).not.toMatch(/RunCanvasNode/);
    expect(source).not.toMatch(/createForkDraftWorkflow/);
  });

  it("removes page-level history mutation so direct loads and back/forward behavior stay under router control", () => {
    const canvasPageSource = fileExists("features/canvas/CanvasPage.tsx")
      ? readSource("features/canvas/CanvasPage.tsx")
      : "";
    const runDetailSource = fileExists("features/runs/RunDetail.tsx")
      ? readSource("features/runs/RunDetail.tsx")
      : "";

    expect(canvasPageSource).not.toMatch(/window\.history\.pushState/);
    expect(canvasPageSource).not.toMatch(/PopStateEvent/);
    expect(runDetailSource).not.toMatch(/window\.history\.pushState/);
    expect(runDetailSource).not.toMatch(/PopStateEvent/);
  });
});
