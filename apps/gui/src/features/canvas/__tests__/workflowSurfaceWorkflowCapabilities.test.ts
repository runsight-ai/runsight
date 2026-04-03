// @vitest-environment jsdom

import { readdirSync, readFileSync } from "node:fs";
import { extname, resolve } from "node:path";
import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { WorkflowSurface } from "../WorkflowSurface";

const GUI_SRC_ROOT = resolve(import.meta.dirname, "../../..");

function readSource(relativePath: string) {
  return readFileSync(resolve(GUI_SRC_ROOT, relativePath), "utf8");
}

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

function candidateDelegatorModules(mode: "workflow" | "historical" | "fork-draft") {
  return collectSourceFiles(GUI_SRC_ROOT).filter((filePath) => {
    const source = readFileSync(filePath, "utf8");

    return (
      /<WorkflowSurface|WorkflowSurface\s*\(|React\.createElement\(\s*WorkflowSurface/.test(
        source,
      )
      && new RegExp(`initialMode\\s*[:=]\\s*["']${mode}["']`).test(source)
    );
  });
}

afterEach(() => {
  cleanup();
});

describe("RUN-593 shared workflow capabilities", () => {
  it("keeps workflow and fork-draft palette/yaml capabilities in the runtime mode contract while historical stays read-only", () => {
    const source = readSource("features/canvas/workflowSurfaceContract.ts");

    expect(source).toMatch(/workflow:[\s\S]*palette:\s*\{\s*visible:\s*true,\s*editable:\s*true\s*\}/);
    expect(source).toMatch(/workflow:[\s\S]*yaml:\s*\{\s*visible:\s*true,\s*editable:\s*true\s*\}/);
    expect(source).toMatch(/"fork-draft":[\s\S]*palette:\s*\{\s*visible:\s*true,\s*editable:\s*true\s*\}/);
    expect(source).toMatch(/"fork-draft":[\s\S]*yaml:\s*\{\s*visible:\s*true,\s*editable:\s*true\s*\}/);
    expect(source).toMatch(/historical:[\s\S]*palette:\s*\{\s*visible:\s*false,\s*editable:\s*false\s*\}/);
    expect(source).toMatch(/historical:[\s\S]*yaml:\s*\{\s*visible:\s*false,\s*editable:\s*false\s*\}/);
  });

  it("renders the shared workflow surface even when a workflow has no blocks yet", () => {
    render(
      React.createElement(WorkflowSurface, {
        initialMode: "workflow",
        workflowId: "wf-empty",
        mainContent: React.createElement("div", null, "No blocks yet"),
      }),
    );

    expect(screen.getByLabelText("workflow surface")).not.toBeNull();
    expect(screen.getByText("No blocks yet")).not.toBeNull();
  });

  it("lets fork-draft mode render an editable shared surface before any run exists", () => {
    render(
      React.createElement(WorkflowSurface, {
        initialMode: "fork-draft",
        workflowId: "wf-draft",
        mainContent: React.createElement("div", null, "Draft yaml editor"),
      }),
    );

    const surface = screen.getByLabelText("workflow surface").closest("[data-layout=\"workflow-surface\"]");

    expect(surface).not.toBeNull();
    expect(surface).toHaveAttribute("data-mode", "fork-draft");
    expect(surface).toHaveAttribute("data-workflow-id", "wf-draft");
    expect(surface).toHaveAttribute("data-editable", "true");
    expect(surface).not.toHaveAttribute("data-run-id");
  });

  it("uses mode-aware yaml or workflow-action rules in the shared surface implementation instead of only palette+center layout rules", () => {
    const source = readSource("features/canvas/WorkflowSurface.tsx");

    expect(source).toMatch(/getWorkflowSurfaceModeConfig/);
    expect(source).toMatch(/regions\.palette\.visible/);
    expect(source).toMatch(/regions\.yaml\.(visible|editable)|actions\.(save|run|fork|openWorkflow)/);
  });

  it("keeps shared-surface entry points for workflow and historical modes on the same component family", () => {
    const workflowEntries = candidateDelegatorModules("workflow");
    const historicalEntries = candidateDelegatorModules("historical");

    expect(workflowEntries.length).toBeGreaterThan(0);
    expect(historicalEntries.length).toBeGreaterThan(0);
  });

  it("adds a fork-draft shared-surface entry path that uses workflow identity without requiring run data", () => {
    const candidates = candidateDelegatorModules("fork-draft");

    expect(candidates.length).toBeGreaterThan(0);

    const source = readFileSync(candidates[0]!, "utf8");
    expect(source).toMatch(/workflowId/);
    expect(source).not.toMatch(/runId\s*[:=]/);
  });
});
