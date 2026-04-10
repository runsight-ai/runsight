import { describe, expect, it } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";

const SRC_DIR = resolve(__dirname, "../../..");

function readSource(relativePath: string): string {
  return readFileSync(resolve(SRC_DIR, relativePath), "utf-8");
}

function rg(pattern: string, cwd = SRC_DIR): string {
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
        cwd,
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

function listSourceFiles(relativeDir: string): string[] {
  const output = execFileSync("rg", ["--files", resolve(SRC_DIR, relativeDir)], {
    encoding: "utf-8",
  }).trim();

  return output ? output.split("\n") : [];
}

describe("RUN-804 surface rename and consolidation", () => {
  it("moves the live surface entrypoint into features/surface", () => {
    expect(existsSync(resolve(SRC_DIR, "features/surface/WorkflowSurface.tsx"))).toBe(true);
    expect(existsSync(resolve(SRC_DIR, "features/canvas/WorkflowSurface.tsx"))).toBe(false);
  });

  it("removes canvas-prefixed shell names from live app source", () => {
    const hits = rg(
      String.raw`^\s*import\s+.*\b(CanvasTopbar|CanvasBottomPanel|CanvasStatusBar|WorkflowCanvas)\b`,
      resolve(SRC_DIR, "features"),
    );

    expect(hits).toBe("");
  });

  it("updates the routes layer to import WorkflowSurface from features/surface", () => {
    const routesSource = readSource("routes/index.tsx");

    expect(routesSource).toMatch(/from "@\/features\/surface\/WorkflowSurface"/);
    expect(routesSource).not.toMatch(/@\/features\/canvas\/WorkflowSurface/);
  });

  it("consolidates features/runs down to RunsPage, RunsTab, and RunRow only", () => {
    const files = listSourceFiles("features/runs")
      .map((file) => file.replace(`${SRC_DIR}/`, ""))
      .filter((file) => !file.includes("/__tests__/"));

    expect(files).toEqual([
      "features/runs/RunRow.tsx",
      "features/runs/RunsPage.tsx",
      "features/runs/RunsTab.tsx",
    ]);
  });

  it("decomposes RunsPage into page, tab, and row modules under 150 lines", () => {
    const source = readSource("features/runs/RunsPage.tsx");
    const lineCount = source.split("\n").length;

    expect(lineCount).toBeLessThan(150);
    expect(source).toMatch(/from "\.\/RunsTab"/);
    expect(source).toMatch(/from "\.\/RunRow"/);
    expect(source).not.toMatch(/from "\.\/RunsTable"/);
  });
});
