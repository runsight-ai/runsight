/**
 * Governance: WorkflowSurface decomposition boundary.
 *
 * Owner: GUI Surface.
 * Boundary: WorkflowSurface stays a thin orchestration shell; runtime behavior
 * belongs in the focused hooks/components covered by behavior tests.
 * Exit criteria: replace this source governance with static architecture rules
 * that enforce the same ownership budgets.
 */

import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const WORKFLOW_SURFACE_PATH = resolve(__dirname, "..", "WorkflowSurface.tsx");

function workflowSurfaceSource(): string {
  return readFileSync(WORKFLOW_SURFACE_PATH, "utf-8");
}

function workflowSurfaceFunctionBody(): string {
  const match = workflowSurfaceSource().match(/export function WorkflowSurface\b[\s\S]*?^}/m);
  expect(match).not.toBeNull();
  return match![0];
}

function logicLineCount(source: string): number {
  return source.split("\n").filter((line) => {
    const trimmed = line.trim();
    return (
      trimmed.length > 0
      && !trimmed.startsWith("//")
      && !trimmed.startsWith("*")
      && !trimmed.startsWith("/*")
    );
  }).length;
}

describe("Governance: WorkflowSurface decomposition boundary", () => {
  it("keeps the component body within the orchestration line budget", () => {
    expect(logicLineCount(workflowSurfaceFunctionBody())).toBeLessThanOrEqual(80);
  });

  it("keeps local state ownership within the orchestration budget", () => {
    const body = workflowSurfaceFunctionBody();
    expect((body.match(/useState[<(]/g) ?? []).length).toBeLessThanOrEqual(6);
  });

  it("keeps side-effect ownership within the orchestration budget", () => {
    const body = workflowSurfaceFunctionBody();
    expect((body.match(/useEffect\(/g) ?? []).length).toBeLessThanOrEqual(3);
  });
});
