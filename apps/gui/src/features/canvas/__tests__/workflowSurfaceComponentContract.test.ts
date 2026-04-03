import { existsSync, readdirSync, readFileSync } from "node:fs";
import { extname, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { describe, expect, it } from "vitest";

const GUI_SRC_ROOT = resolve(import.meta.dirname, "../../..");
const CANVAS_PAGE_PATH = resolve(import.meta.dirname, "../CanvasPage.tsx");
const RUN_DETAIL_PATH = resolve(import.meta.dirname, "../../runs/RunDetail.tsx");

function collectSourceFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const fullPath = resolve(dir, entry.name);

    if (entry.isDirectory()) {
      if (entry.name === "__tests__") {
        return [];
      }

      return collectSourceFiles(fullPath);
    }

    const extension = extname(entry.name);
    if (![".ts", ".tsx"].includes(extension) || entry.name.endsWith(".d.ts")) {
      return [];
    }

    return [fullPath];
  });
}

function candidateWorkflowSurfaceModules() {
  return collectSourceFiles(GUI_SRC_ROOT).filter((filePath) => {
    const source = readFileSync(filePath, "utf8");

    return (
      source.includes("WorkflowSurface")
      && source.includes("WorkflowSurfaceProps")
      && source.includes("getWorkflowSurfaceModeConfig")
      && /export\s+(function|const)\s+(WorkflowSurface|Component)|export\s+default/.test(
        source,
      )
    );
  });
}

async function loadWorkflowSurfaceModule() {
  const candidates = candidateWorkflowSurfaceModules();

  expect(candidates.length).toBeGreaterThan(0);

  for (const candidate of candidates) {
    const module = (await import(pathToFileURL(candidate).href)) as Record<
      string,
      unknown
    >;

    if (
      typeof module.Component === "function"
      || typeof module.WorkflowSurface === "function"
      || typeof module.default === "function"
    ) {
      return { candidate, source: readFileSync(candidate, "utf8"), module };
    }
  }

  throw new Error(
    "Expected a GUI source module to export a shared WorkflowSurface component",
  );
}

describe("RUN-592 WorkflowSurface component contract", () => {
  it("creates a shared WorkflowSurface page-level component that consumes the RUN-591 runtime contract", async () => {
    const { source } = await loadWorkflowSurfaceModule();

    expect(source).toMatch(/WorkflowSurfaceProps/);
    expect(source).toMatch(/getWorkflowSurfaceModeConfig/);
    expect(source).toMatch(/topbar|header/i);
    expect(source).toMatch(/inspector/i);
    expect(source).toMatch(/footer|bottom/i);
    expect(source).toMatch(/status/i);
  });

  it("moves CanvasPage behind WorkflowSurface in workflow mode instead of keeping a separate page architecture", () => {
    expect(existsSync(CANVAS_PAGE_PATH)).toBe(true);

    const source = readFileSync(CANVAS_PAGE_PATH, "utf8");

    expect(source).toMatch(
      /<WorkflowSurface|WorkflowSurface\s*\(|React\.createElement\(\s*WorkflowSurface/,
    );
    expect(source).toMatch(/initialMode\s*[:=]\s*["']workflow["']/);
    expect(source).toMatch(/workflowId/);
  });

  it("moves RunDetail behind WorkflowSurface in historical mode instead of preserving a separate run page surface", () => {
    expect(existsSync(RUN_DETAIL_PATH)).toBe(true);

    const source = readFileSync(RUN_DETAIL_PATH, "utf8");

    expect(source).toMatch(
      /<WorkflowSurface|WorkflowSurface\s*\(|React\.createElement\(\s*WorkflowSurface/,
    );
    expect(source).toMatch(/initialMode\s*[:=]\s*["']historical["']/);
    expect(source).toMatch(/runId/);
  });

  it("keeps workflow-only and run-only entry points delegating to the same shared surface", () => {
    const canvasSource = readFileSync(CANVAS_PAGE_PATH, "utf8");
    const runSource = readFileSync(RUN_DETAIL_PATH, "utf8");

    expect(canvasSource).toMatch(
      /<WorkflowSurface|WorkflowSurface\s*\(|React\.createElement\(\s*WorkflowSurface/,
    );
    expect(runSource).toMatch(
      /<WorkflowSurface|WorkflowSurface\s*\(|React\.createElement\(\s*WorkflowSurface/,
    );
    expect(canvasSource).toMatch(/workflowId/);
    expect(runSource).toMatch(/runId/);
  });
});
