/**
 * Governance: packages/ui Storybook configuration and tooling must be owned by
 * a behavior-named package UI suite.
 * Owner: packages/ui Storybook config and package tooling checks.
 * Boundary: source-text checks for packages/ui/.storybook and
 * packages/ui/package.json only; DesignTokens story surface checks belong in
 * designTokenStorySurface.test.ts.
 * Exit criteria: remove this suite once repo-boundary tooling enforces
 * Storybook config ownership and package tooling requirements for packages/ui.
 */

import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const TEST_DIR = dirname(fileURLToPath(import.meta.url));
const PACKAGE_UI_ROOT = resolve(TEST_DIR, "..", "..", "..");
const STORYBOOK_DIR = resolve(PACKAGE_UI_ROOT, ".storybook");
const MAIN_TS = resolve(STORYBOOK_DIR, "main.ts");
const PREVIEW_TS = resolve(STORYBOOK_DIR, "preview.ts");
const PACKAGE_JSON = resolve(PACKAGE_UI_ROOT, "package.json");

function readFile(filePath: string): string {
  return readFileSync(filePath, "utf-8");
}

function readPackageJson(): {
  scripts?: Record<string, string>;
  devDependencies?: Record<string, string>;
} {
  return JSON.parse(readFile(PACKAGE_JSON));
}

describe(".storybook/main.ts Storybook framework config", () => {
  it("exists at packages/ui/.storybook/main.ts", () => {
    expect(existsSync(MAIN_TS)).toBe(true);
  });

  it("uses @storybook/react-vite as the framework", () => {
    const content = readFile(MAIN_TS);
    expect(content).toMatch(/@storybook\/react-vite/);
  });

  it("loads stories from package UI src story files", () => {
    const content = readFile(MAIN_TS);
    expect(content).toMatch(/\.\.\/src\/\*\*\/\*\.stories/);
    expect(content).toMatch(/tsx/);
  });

  it("wires @tailwindcss/vite for Tailwind v4 token support", () => {
    const content = readFile(MAIN_TS);
    expect(content).toMatch(/@tailwindcss\/vite/);
  });
});

describe(".storybook/preview.ts design system setup", () => {
  it("exists at packages/ui/.storybook/preview.ts", () => {
    expect(existsSync(PREVIEW_TS)).toBe(true);
  });

  it("imports the package UI globals.css token stylesheet", () => {
    const content = readFile(PREVIEW_TS);
    expect(content).toMatch(/\.\.\/src\/styles\/globals\.css/);
  });

  it("sets dark as the default Storybook background", () => {
    const content = readFile(PREVIEW_TS);
    expect(content).toMatch(/backgrounds/);
    expect(content).toMatch(/dark/);
  });

  it("defines a named dark background with a color value", () => {
    const content = readFile(PREVIEW_TS);
    expect(content).toMatch(/name.*dark|dark.*name/i);
    expect(content).toMatch(/value\s*:/);
  });

  it("documents the fonts loaded by the package UI token stylesheet", () => {
    const content = readFile(PREVIEW_TS);
    expect(content).toMatch(/[Gg]eist/);
    expect(content).toMatch(/[Jj]et[Bb]rains/);
    expect(content).toMatch(/[Ss]atoshi/);
  });
});

describe("package.json Storybook scripts", () => {
  it("defines a storybook dev script on port 6006", () => {
    const pkg = readPackageJson();
    expect(pkg.scripts?.["storybook"]).toBeDefined();
    expect(pkg.scripts?.["storybook"]).toMatch(/storybook\s+dev/);
    expect(pkg.scripts?.["storybook"]).toMatch(/-p\s*6006|--port\s*6006/);
  });

  it("defines a build-storybook script", () => {
    const pkg = readPackageJson();
    expect(pkg.scripts?.["build-storybook"]).toBeDefined();
    expect(pkg.scripts?.["build-storybook"]).toMatch(/storybook\s+build/);
  });
});

describe("package.json Storybook devDependencies", () => {
  it("declares Storybook packages in devDependencies", () => {
    const pkg = readPackageJson();
    expect(pkg.devDependencies?.["@storybook/react-vite"]).toBeDefined();
    expect(pkg.devDependencies?.["storybook"]).toBeDefined();
  });

  it("keeps Storybook package versions on 8.x or later", () => {
    const pkg = readPackageJson();
    const reactViteVersion = pkg.devDependencies?.["@storybook/react-vite"] ?? "";
    const storybookVersion = pkg.devDependencies?.["storybook"] ?? "";

    expect(reactViteVersion).toMatch(/^[\^~]?[89]|>=\s*[89]/);
    expect(storybookVersion).toMatch(/^[\^~]?[89]|>=\s*[89]/);
  });
});
