/**
 * Governance: retired task surface boundary.
 *
 * Owner: GUI Surface.
 * Boundary: task nodes and task sidebar tabs must not re-enter the surface UI.
 * Exit criteria: replace this source/layout governance with generated route and
 * canvas-schema ownership checks that fail at compile time.
 */

import { describe, expect, it } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { nodeTypes } from "../nodes";

const SURFACE_DIR = resolve(__dirname, "..");
const GUI_SRC_DIR = resolve(__dirname, "../../..");

function readGuiSource(relativePath: string): string {
  return readFileSync(resolve(GUI_SRC_DIR, relativePath), "utf-8");
}

describe("Governance: retired task surface boundary", () => {
  it("does not ship a TaskNode component in the surface node directory", () => {
    expect(existsSync(resolve(SURFACE_DIR, "nodes/TaskNode.tsx"))).toBe(false);
  });

  it("does not register a task node type in the surface canvas", () => {
    expect(Object.keys(nodeTypes)).not.toContain("task");
    expect(nodeTypes).not.toHaveProperty("task");
  });

  it("does not keep retired task node labels or minimap colors in surface rendering", () => {
    const nodeCardSource = readGuiSource("features/surface/nodes/SurfaceNodeCard.tsx");
    const canvasSource = readGuiSource("features/surface/SurfaceCanvas.tsx");

    expect(nodeCardSource).not.toContain('"task"');
    expect(nodeCardSource).not.toContain("TASK");
    expect(canvasSource).not.toContain('case "task"');
    expect(canvasSource).not.toContain("var(--task)");
  });

  it("keeps the left sidebar tab contract free of retired tasks", () => {
    const canvasSchema = readGuiSource("types/schemas/canvas.ts");
    const declaration = canvasSchema.match(/export type LeftSidebarTab\s*=\s*[^;]+;/)?.[0] ?? "";

    expect(declaration).toBeTruthy();
    expect(declaration).not.toContain('"tasks"');
  });
});
