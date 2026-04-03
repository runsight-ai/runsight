import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const GUI_SRC_ROOT = resolve(import.meta.dirname, "../../..");

function readSource(relativePath: string) {
  return readFileSync(resolve(GUI_SRC_ROOT, relativePath), "utf8");
}

const WORKFLOW_SURFACE_PATH = "features/canvas/WorkflowSurface.tsx";
const WORKFLOW_SURFACE_CONTRACT_PATH = "features/canvas/workflowSurfaceContract.ts";
const CANVAS_PAGE_PATH = "features/canvas/CanvasPage.tsx";

describe("RUN-593 shared workflow capabilities", () => {
  it("keeps workflow and fork-draft palette/yaml capabilities in the runtime mode contract while historical stays read-only", () => {
    const source = readSource(WORKFLOW_SURFACE_CONTRACT_PATH);

    expect(source).toMatch(/workflow:[\s\S]*palette:\s*\{\s*visible:\s*true,\s*editable:\s*true\s*\}/);
    expect(source).toMatch(/workflow:[\s\S]*yaml:\s*\{\s*visible:\s*true,\s*editable:\s*true\s*\}/);
    expect(source).toMatch(/"fork-draft":[\s\S]*palette:\s*\{\s*visible:\s*true,\s*editable:\s*true\s*\}/);
    expect(source).toMatch(/"fork-draft":[\s\S]*yaml:\s*\{\s*visible:\s*true,\s*editable:\s*true\s*\}/);
    expect(source).toMatch(/historical:[\s\S]*center:\s*\{\s*visible:\s*true,\s*editable:\s*false\s*\}/);
    expect(source).toMatch(/historical:[\s\S]*palette:\s*\{\s*visible:\s*false,\s*editable:\s*false\s*\}/);
    expect(source).toMatch(/historical:[\s\S]*yaml:\s*\{\s*visible:\s*false,\s*editable:\s*false\s*\}/);
  });

  it("moves palette, yaml editor, and workflow action ownership into WorkflowSurface instead of leaving it as a passive layout shell", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);

    expect(source).toMatch(/PaletteSidebar/);
    expect(source).toMatch(/YamlEditor/);
    expect(source).toMatch(/actions\.(save|run)|actions:\s*\{[\s\S]*(save|run)/);
    expect(source).toMatch(/<button|<Button|onClick=/);
  });

  it("drives workflow-only affordances from mode-aware WorkflowSurface rendering so workflow and fork-draft share the same implementation path", () => {
    const source = readSource(WORKFLOW_SURFACE_PATH);

    expect(source).toMatch(/regions\.palette\.visible/);
    expect(source).toMatch(/regions\.yaml\.visible/);
    expect(source).toMatch(/editable/);
    expect(source).toMatch(/fork-draft|supportsSameSurfaceTransition|routeChangeRequired/);
  });

  it("stops CanvasPage from directly importing and rendering workflow-only capability components once WorkflowSurface owns them", () => {
    const source = readSource(CANVAS_PAGE_PATH);

    expect(source).not.toMatch(/import\s+\{?\s*PaletteSidebar\b/);
    expect(source).not.toMatch(/import\s+\{?\s*YamlEditor\b/);
    expect(source).not.toMatch(/<PaletteSidebar\b/);
    expect(source).not.toMatch(/<YamlEditor\b/);
  });

  it("keeps CanvasPage as a thin workflow entry delegator instead of composing shared-surface regions and edit actions itself", () => {
    const source = readSource(CANVAS_PAGE_PATH);

    expect(source).toMatch(/<WorkflowSurface/);
    expect(source).toMatch(/initialMode="workflow"/);
    expect(source).toMatch(/workflowId=\{id!\}/);
    expect(source).not.toMatch(/\b(topbar|palette|mainContent|footer|statusBar)\s*=/);
    expect(source).not.toMatch(/CommitDialog|ProviderModal|useCreateRun|gitApi/);
  });
});
