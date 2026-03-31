import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const ROUTES_PATH = resolve(__dirname, "..", "index.tsx");
const SHELL_LAYOUT_PATH = resolve(__dirname, "..", "layouts", "ShellLayout.tsx");

function readSource(path: string): string {
  return readFileSync(path, "utf-8");
}

describe("RUN-426 /flows route contract", () => {
  it("adds a /flows route that lazy loads the new FlowsPage feature shell", () => {
    const source = readSource(ROUTES_PATH);

    expect(source).toMatch(/path:\s*["']flows["']/);
    expect(source).toMatch(/import\("@\/features\/flows\/FlowsPage"\)/);
  });

  it("keeps workflow editor navigation on /workflows/:id/edit for row opens", () => {
    const source = readSource(ROUTES_PATH);

    expect(source).toMatch(/path:\s*["']workflows\/:id\/edit["']/);
    expect(source).toMatch(/CanvasPage/);
  });

  it("points the sidebar Flows nav item at /flows instead of the legacy /workflows list", () => {
    const source = readSource(SHELL_LAYOUT_PATH);

    expect(source).toMatch(/to:\s*["']\/flows["'][\s\S]*label:\s*["']Flows["']/);
    expect(source).not.toMatch(/to:\s*["']\/workflows["'][\s\S]*label:\s*["']Flows["']/);
  });
});
