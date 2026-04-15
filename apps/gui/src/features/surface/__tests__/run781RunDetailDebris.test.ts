// @vitest-environment jsdom

import { describe, expect, it } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";

const SRC_DIR = resolve(__dirname, "../../..");
const CANVAS_DIR = resolve(__dirname, "..");
const ROUTES_FILE = resolve(SRC_DIR, "routes/index.tsx");

function readCanvasSource(relativePath: string): string {
  return readFileSync(resolve(CANVAS_DIR, relativePath), "utf-8");
}

function readRoutesSource(): string {
  return readFileSync(ROUTES_FILE, "utf-8");
}

function searchWorkspace(pattern: string): string {
  try {
    return execFileSync(
      "rg",
      [
        "-n",
        "--glob",
        "!**/__tests__/**",
        "--glob",
        "!**/*.test.ts",
        "--glob",
        "!**/*.test.tsx",
        pattern,
        SRC_DIR,
      ],
      { encoding: "utf-8" },
    ).trim();
  } catch (error) {
    const status = (error as { status?: number }).status;
    if (status === 1) {
      return "";
    }

    throw error;
  }
}

describe("RunDetail debris cleanup in the canvas surface (RUN-781)", () => {
  it("moves shared run-detail utilities and inspector wiring into canvas-owned modules", () => {
    const workflowSurface = readCanvasSource("WorkflowSurface.tsx");

    // surfaceUtils may be imported by WorkflowSurface directly or via a decomposed hook
    const useNodeStatus = readCanvasSource("useNodeStatusMapping.ts");
    const surfaceUtilsIsUsed =
      /from "\.\/surfaceUtils"/.test(workflowSurface) ||
      /from "\.\/surfaceUtils"/.test(useNodeStatus);
    expect(surfaceUtilsIsUsed).toBe(true);
    expect(workflowSurface).toMatch(/from "\.\/SurfaceInspectorPanel"/);
    expect(workflowSurface).not.toMatch(/@\/features\/runs\/runDetailUtils/);
    expect(workflowSurface).not.toMatch(/@\/features\/runs\/RunInspectorPanel/);
  });

  it("moves RunDetail, RunDetailHeader, RunInspectorPanel, RunCanvasNode, and runDetailUtils off the runs tree", () => {
    for (const relativePath of [
      "../runs/RunDetail.tsx",
      "../runs/RunDetailHeader.tsx",
      "../runs/RunInspectorPanel.tsx",
      "../runs/RunCanvasNode.tsx",
      "../runs/runDetailUtils.ts",
    ]) {
      expect(existsSync(resolve(CANVAS_DIR, relativePath))).toBe(false);
    }

    expect(existsSync(resolve(CANVAS_DIR, "SurfaceInspectorPanel.tsx"))).toBe(true);
  });

  it("exposes mapRunStatus and getIconForBlockType from features/surface/surfaceUtils.ts", () => {
    const surfaceUtilsPath = resolve(CANVAS_DIR, "surfaceUtils.ts");

    expect(existsSync(surfaceUtilsPath)).toBe(true);
    const surfaceUtils = readCanvasSource("surfaceUtils.ts");
    expect(surfaceUtils).toMatch(/export function mapRunStatus\b/);
    expect(surfaceUtils).toMatch(/export function getIconForBlockType\b/);
  });

  it("keeps /runs/:id rendering WorkflowSurface instead of RunDetail", () => {
    const routesSource = readRoutesSource();
    expect(routesSource).toMatch(
      /function\s+ReadonlyRunRoute\(\)[\s\S]*<WorkflowSurface\s+mode="readonly"\s+runId=\{id!\}\s*\/>/,
    );
    expect(routesSource).not.toMatch(/features\/runs\/RunDetail/);
  });

  it("removes deleted RunDetail-era import statements from apps/gui/src", () => {
    const matches = searchWorkspace(
      String.raw`^\s*import\s+.*(?:RunDetail|RunDetailHeader|RunInspectorPanel|RunCanvasNode|RunBottomPanel|runDetailUtils)`,
    );

    expect(matches).toBe("");
  });

  it("removes buildCanvasFromRun references from apps/gui/src", () => {
    const matches = searchWorkspace(String.raw`^\s*(?:const|function|useEffect|buildCanvasFromRun)\b.*buildCanvasFromRun(?:Nodes)?\b`);

    expect(matches).toBe("");
  });
});
