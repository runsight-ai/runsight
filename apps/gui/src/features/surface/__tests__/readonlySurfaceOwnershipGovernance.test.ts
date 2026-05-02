/**
 * Governance: readonly surface test ownership boundary.
 *
 * Owner: GUI Surface.
 * Boundary: readonlySurfaceIntegration.test.tsx owns detailed readonly
 * behavior, sharedCanvasPath.test.tsx owns only the canonical WorkflowCanvas
 * host/path contract, and testing/gui-e2e/tests/readonly-surface.spec.ts stays
 * browser-smoke level with its runtime fixture setup delegated to named E2E
 * helpers or fixtures.
 * Exit criteria: remove once these ownership boundaries are enforced by a
 * shared test-layout manifest or repo-wide governance tooling.
 */

import { describe, expect, it } from "vitest";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { resolve, relative } from "node:path";

const SURFACE_TEST_DIR = __dirname;
const REPO_ROOT = resolve(SURFACE_TEST_DIR, "../../../../../..");
const E2E_TEST_DIR = resolve(REPO_ROOT, "testing/gui-e2e/tests");
const E2E_READONLY_SPEC = resolve(E2E_TEST_DIR, "readonly-surface.spec.ts");
const GUI_READONLY_OWNER = resolve(SURFACE_TEST_DIR, "readonlySurfaceIntegration.test.tsx");
const SHARED_CANVAS_PATH_SUITE = resolve(SURFACE_TEST_DIR, "sharedCanvasPath.test.tsx");

type SourceFile = {
  relativePath: string;
  source: string;
};

function read(path: string): string {
  return readFileSync(path, "utf-8");
}

function readFilesRecursive(root: string): SourceFile[] {
  if (!existsSync(root)) {
    return [];
  }

  return readdirSync(root).flatMap((entry) => {
    const path = resolve(root, entry);
    const stats = statSync(path);

    if (stats.isDirectory()) {
      return readFilesRecursive(path);
    }

    if (!/\.[cm]?tsx?$/.test(entry)) {
      return [];
    }

    return [
      {
        relativePath: relative(E2E_TEST_DIR, path),
        source: read(path),
      },
    ];
  });
}

function matchingLines(source: string, pattern: RegExp): string[] {
  return source
    .split("\n")
    .map((line, index) => ({ line, index }))
    .filter(({ line }) => pattern.test(line))
    .map(({ line, index }) => `${index + 1}: ${line.trim()}`);
}

function markerHits(source: string, markers: Array<string | RegExp>): string[] {
  return markers.flatMap((marker) => {
    if (typeof marker === "string") {
      return matchingLines(source, new RegExp(escapeRegExp(marker)));
    }

    return matchingLines(source, marker);
  });
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

describe("Governance: readonly surface test ownership boundary", () => {
  it("delegates E2E readonly run and canvas fixture seeding to named helper or fixture files", () => {
    const readonlyFixtureOwners = [
      ...readFilesRecursive(resolve(E2E_TEST_DIR, "fixtures")),
      ...readFilesRecursive(resolve(E2E_TEST_DIR, "helpers")),
    ].filter(({ relativePath, source }) => {
      const namesReadonlySurfaceBehavior =
        /(?:^|\/)(?:readonly[-A-Za-z0-9]*surface|surface[-A-Za-z0-9]*readonly|readonly[-A-Za-z0-9]*run|run[-A-Za-z0-9]*readonly)[-A-Za-z0-9]*\.[cm]?tsx?$/.test(
          relativePath,
        );
      const ownsReadonlyFixtureBehavior =
        /readonly surface fixture|readonly run fixture|readonly canvas fixture|seedReadonly(?:Run|Canvas)Fixture/i.test(
          source,
        );

      return namesReadonlySurfaceBehavior || ownsReadonlyFixtureBehavior;
    });

    expect(readonlyFixtureOwners.map(({ relativePath }) => relativePath).sort()).not.toEqual([]);
  });

  it("keeps direct DB, canvas sidecar, and YAML fixture seeding out of the E2E spec", () => {
    const e2eSource = read(E2E_READONLY_SPEC);
    const forbiddenFixtureSeeding = markerHits(e2eSource, [
      "execFileSync",
      "runsight.db",
      /INSERT(?:\s+OR\s+REPLACE)?\s+INTO/i,
      /DELETE\s+FROM/i,
      "resolveE2ERuntimePath",
      /["']\.canvas["']/,
      "SEEDED_WORKFLOW_YAML",
      "SEEDED_CANVAS_STATE",
      "seedReadonlyRunFixture",
      "seedReadonlyCanvasFixture",
      "cleanupReadonlyRunFixture",
      "cleanupReadonlyCanvasFixture",
    ]);

    expect(forbiddenFixtureSeeding).toEqual([]);
  });

  it("keeps readonly-surface E2E browser-smoke level instead of detailed readonly behavior ownership", () => {
    const e2eSource = read(E2E_READONLY_SPEC);
    const forbiddenDetailedReadonlyAssertions = markerHits(e2eSource, [
      "/api/git/file",
      "historicalYaml",
      "readVisibleYaml",
      "right-inspector",
      "Dismiss banner",
      "Canvas layout unavailable",
      "canvas_state is missing",
      "direct edit route exposes",
      "supports canvas, yaml, inspector, regressions, and fork",
      "regressions found",
    ]);

    expect(forbiddenDetailedReadonlyAssertions).toEqual([]);
  });

  it("keeps the GUI readonly integration suite as the detailed readonly behavior owner", () => {
    const readonlySource = read(GUI_READONLY_OWNER);

    expect(readonlySource).toContain("shows historical YAML from the run commit");
    expect(readonlySource).toContain("harness.getGitFile");
    expect(readonlySource).toContain("opens the shared inspector on node click and closes it on pane click");
    expect(readonlySource).toContain("right-inspector");
    expect(readonlySource).toContain("shows the readonly regressions banner only when regressions are present");
    expect(readonlySource).toContain("regressions found");
    expect(readonlySource).toContain("lays out readonly canvas from YAML when canvas_state is missing");
    expect(readonlySource).toContain("Canvas layout unavailable");
    expect(readonlySource).toContain(
      "navigates a readonly run fork through the router into the editable workflow route",
    );
    expect(readonlySource).toContain("keeps edit mode off the readonly data path");
    expect(readonlySource).toContain("not.toHaveBeenCalled()");
  });

  it("keeps sharedCanvasPath limited to canonical WorkflowCanvas host/path ownership", () => {
    const sharedCanvasPathSource = read(SHARED_CANVAS_PATH_SUITE);
    const forbiddenDetailedReadonlyDuplication = markerHits(sharedCanvasPathSource, [
      "right-inspector",
      "regressions found",
      "getGitFile",
      "Historical Snapshot",
      "Fork",
      "Run failed before execution started",
    ]);

    expect(forbiddenDetailedReadonlyDuplication).toEqual([]);
  });
});
