/**
 * RED-TEAM tests for RUN-777: readonly route wiring + canonical data loading.
 *
 * These assertions are intentionally narrow and source-oriented because the
 * current implementation does not expose a readonly surface harness yet.
 * They should fail until the readonly route and WorkflowSurface data path are
 * implemented.
 */

import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const CANVAS_DIR = resolve(__dirname, "..");
const ROUTES_DIR = resolve(__dirname, "../../../routes");

function readCanvasFile(relativePath: string): string {
  return readFileSync(resolve(CANVAS_DIR, relativePath), "utf-8");
}

function readRoutesFile(relativePath: string): string {
  return readFileSync(resolve(ROUTES_DIR, relativePath), "utf-8");
}

describe("routes/index.tsx readonly run route (RUN-777 AC1)", () => {
  const source = readRoutesFile("index.tsx");

  it("does not keep /runs/:id wired to the legacy run-detail route module", () => {
    const runRouteBlock = source.match(
      /path:\s*"runs\/:id"[\s\S]*?(?=\n\s*\},\n\s*\{|\n\s*\}\s*,\n\s*\{)/,
    )?.[0] ?? "";

    expect(runRouteBlock).not.toMatch(/features\/runs\/RunDetail/);
  });

  it("defines a readonly route component that renders WorkflowSurface in readonly mode", () => {
    expect(source).toMatch(/function\s+ReadonlyRunRoute\s*\(/);
    expect(source).toMatch(/<WorkflowSurface\s+mode="readonly"/);
  });

  it("passes the router param through as runId", () => {
    expect(source).toMatch(/useParams<\{\s*id:\s*string\s*\}>/);
    expect(source).toMatch(/runId=\{id!?}/);
  });
});

describe("WorkflowSurface readonly data loading (RUN-777 AC1-AC5)", () => {
  const source = readCanvasFile("WorkflowSurface.tsx");

  it("reads run data in readonly mode via useRun", () => {
    expect(source).toMatch(/useRun\(/);
  });

  it("polls readonly runs every 2 seconds while they are active", () => {
    expect(source).toMatch(/refetchInterval[\s\S]*2000/);
  });

  it("reads per-node execution state via useRunNodes", () => {
    expect(source).toMatch(/useRunNodes\(/);
  });

  it("loads workflow data after resolving run.workflow_id", () => {
    expect(source).toMatch(/run\?\.workflow_id|run\.workflow_id/);
    expect(source).toMatch(/useWorkflow\(/);
  });

  it("hydrates from persisted canvas_state instead of rebuilding topology from run nodes", () => {
    // hydrateFromPersisted is extracted to useCanvasHydration; check surface + hook
    const hydrationSource = readCanvasFile("useCanvasHydration.ts");
    expect(hydrationSource).toMatch(/hydrateFromPersisted\(/);
    expect(source).not.toMatch(/buildCanvasFromRunNodes|buildCanvasFromRun/);
  });

  it("overlays readonly execution state through canvas-store updates", () => {
    expect(source).toMatch(/setNodeStatus|setActiveRunId|setRunCost/);
  });

  it("loads historical YAML from run.commit_sha instead of only overlayRef search params", () => {
    // gitApi.getGitFile is extracted to useReadonlyRunYaml; check surface + hook
    const readonlyYamlSource = readCanvasFile("useReadonlyRunYaml.ts");
    // The call may be split across lines (gitApi\n  .getGitFile), so check separately
    expect(readonlyYamlSource).toMatch(/getGitFile\(/);
    expect(readonlyYamlSource).toMatch(/run\??\.commit_sha/);
    expect(source).toMatch(/<SurfaceYamlEditor[\s\S]*yaml=/);
  });

  it("keeps readonly YAML rendering read-only", () => {
    expect(source).toMatch(
      /<SurfaceYamlEditor[\s\S]*readOnly=\{[^}]*true|<SurfaceYamlEditor[\s\S]*readOnly/,
    );
  });

  it("shows an explicit readonly loading state for runs", () => {
    expect(source).toMatch(/Loading run details\.\.\./);
  });

  it("shows a run-scoped not-found state with a back link to /runs", () => {
    expect(source).toMatch(/Run not found/);
    expect(source).toMatch(/Back to runs/);
    expect(source).toMatch(/to="\/runs"/);
  });

  it("renders a graceful fallback when canvas_state is unavailable instead of synthetic coordinates", () => {
    expect(source).toMatch(/layout unavailable|canvas layout unavailable|canvas unavailable/i);
    expect(source).not.toMatch(/x:\s*100\s*\+\s*\(index\s*%\s*3\)\s*\*\s*300/);
  });
});
