import { readdirSync, readFileSync } from "node:fs";
import { extname, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { describe, expect, it } from "vitest";

const GUI_SRC_ROOT = resolve(import.meta.dirname, "../../..");

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
      && /workflowId|runId/.test(source)
      && /workflow|historical/.test(source)
      && /topbar|header/i.test(source)
      && /inspector/i.test(source)
      && /footer|bottom/i.test(source)
      && /status/i.test(source)
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

function candidateDelegatorModules(mode: "workflow" | "historical", idName: "workflowId" | "runId") {
  return collectSourceFiles(GUI_SRC_ROOT).filter((filePath) => {
    const source = readFileSync(filePath, "utf8");

    return (
      /<WorkflowSurface|WorkflowSurface\s*\(|React\.createElement\(\s*WorkflowSurface/.test(
        source,
      )
      && new RegExp(`initialMode\\s*[:=]\\s*["']${mode}["']`).test(source)
      && source.includes(idName)
    );
  });
}

describe("RUN-592 WorkflowSurface component contract", () => {
  it("creates a shared WorkflowSurface page-level component that can host both workflow and run surfaces without fixing one exact RUN-591 api spelling", async () => {
    const { source } = await loadWorkflowSurfaceModule();

    expect(source).toMatch(/workflowId/);
    expect(source).toMatch(/runId/);
    expect(source).toMatch(/workflow/);
    expect(source).toMatch(/historical/);
    expect(source).toMatch(/topbar|header/i);
    expect(source).toMatch(/inspector/i);
    expect(source).toMatch(/footer|bottom/i);
    expect(source).toMatch(/status/i);
  });

  it("provides a workflow-mode entry path that loads the shared surface with only a workflow identifier, covering workflow mode without run data", () => {
    const candidates = candidateDelegatorModules("workflow", "workflowId");

    expect(candidates.length).toBeGreaterThan(0);

    const source = readFileSync(candidates[0]!, "utf8");
    expect(source).toMatch(/initialMode\s*[:=]\s*["']workflow["']/);
    expect(source).toMatch(/workflowId/);
    expect(source).not.toMatch(/runId\s*[:=]/);
  });

  it("provides a historical-mode entry path that loads the shared surface with only a run identifier, covering missing workflow edit capabilities", () => {
    const candidates = candidateDelegatorModules("historical", "runId");

    expect(candidates.length).toBeGreaterThan(0);

    const source = readFileSync(candidates[0]!, "utf8");
    expect(source).toMatch(/initialMode\s*[:=]\s*["']historical["']/);
    expect(source).toMatch(/runId/);
    expect(source).not.toMatch(/workflowId\s*[:=]/);
  });

  it("keeps one shared surface while still modeling the RUN-592 single-identifier and missing-capability edge cases", async () => {
    const workflowEntries = candidateDelegatorModules("workflow", "workflowId");
    const historicalEntries = candidateDelegatorModules("historical", "runId");
    const { source } = await loadWorkflowSurfaceModule();

    expect(workflowEntries.length).toBeGreaterThan(0);
    expect(historicalEntries.length).toBeGreaterThan(0);
    expect(source).toMatch(/overlay|run data|hasRunOverlay|usesRunOverlay/i);
    expect(source).toMatch(/readOnly|editable|edit/i);
  });
});
