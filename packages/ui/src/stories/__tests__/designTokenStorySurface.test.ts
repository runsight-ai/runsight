/**
 * Governance: packages/ui DesignTokens documentation stories must be owned by
 * a behavior-named package UI suite.
 * Owner: packages/ui DesignTokens documentation story surface checks.
 * Boundary: source-text checks for packages/ui/src/stories/DesignTokens.stories.tsx
 * only; Storybook config and package tooling checks belong in
 * storybookConfig.test.ts.
 * Exit criteria: remove this suite once visual documentation coverage is
 * enforced by Storybook composition, interaction tests, or design-token docs
 * generation.
 */

import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const TEST_DIR = dirname(fileURLToPath(import.meta.url));
const PACKAGE_UI_ROOT = resolve(TEST_DIR, "..", "..", "..");
const DESIGN_TOKENS_STORY = resolve(
  PACKAGE_UI_ROOT,
  "src",
  "stories",
  "DesignTokens.stories.tsx",
);

function readDesignTokensStory(): string {
  return readFileSync(DESIGN_TOKENS_STORY, "utf-8");
}

describe("DesignTokens.stories.tsx Storybook structure", () => {
  it("exists at packages/ui/src/stories/DesignTokens.stories.tsx", () => {
    expect(existsSync(DESIGN_TOKENS_STORY)).toBe(true);
  });

  it("exports Storybook meta with a title", () => {
    const content = readDesignTokensStory();
    expect(content).toMatch(/export\s+default\s+/);
    expect(content).toMatch(/title\s*:/);
  });

  it("exports named documentation stories", () => {
    const content = readDesignTokensStory();
    expect(content).toMatch(/export\s+const\s+\w+/);
  });
});

describe("DesignTokens.stories.tsx documentation surface", () => {
  it("shows color palette documentation for neutral, accent, and semantic tokens", () => {
    const content = readDesignTokensStory();
    expect(content).toMatch(/color palette|neutral|accent|semantic tokens/i);
    expect(content).toMatch(/neutral/i);
    expect(content).toMatch(/accent/i);
    expect(content).toMatch(/success|warning|danger|info/i);
  });

  it("shows typography scale documentation", () => {
    const content = readDesignTokensStory();
    expect(content).toMatch(/typography|font-size|heading|type scale/i);
  });

  it("shows spacing scale documentation", () => {
    const content = readDesignTokensStory();
    expect(content).toMatch(/spacing|space-|gap|padding/i);
  });
});
