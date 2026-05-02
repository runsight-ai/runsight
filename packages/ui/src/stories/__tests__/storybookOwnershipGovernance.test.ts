/**
 * Governance: packages/ui Storybook setup coverage must have behavior-owned
 * suites instead of a mixed setup bucket.
 * Owner: packages/ui Storybook configuration and design-token story coverage.
 * Boundary: source-text governance for package UI story tests only; this suite
 * separates Storybook config/tooling checks from DesignTokens documentation
 * story surface checks.
 * Exit criteria: remove this once lint or repo-boundary tooling enforces
 * behavior-named owners and governance metadata for these package UI story
 * suites.
 */

import { existsSync, readFileSync, readdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const TEST_DIR = dirname(fileURLToPath(import.meta.url));
const LEGACY_SETUP_SUITE = resolve(TEST_DIR, "storybookSetup.test.ts");

const REQUIRED_METADATA = [
  "Governance:",
  "Owner:",
  "Boundary:",
  "Exit criteria:",
] as const;

const REQUIRED_OWNER_SUITES = [
  {
    filename: "storybookConfig.test.ts",
    scope: "Storybook config and package tooling",
    requiredPatterns: [
      /\.storybook\/main\.ts/,
      /\.storybook\/preview\.ts/,
      /package\.json/,
      /@storybook\/react-vite/,
      /storybook\s+dev/,
    ],
    forbiddenPatterns: [/DesignTokens\.stories\.tsx/],
  },
  {
    filename: "designTokenStorySurface.test.ts",
    scope: "DesignTokens documentation story surface",
    requiredPatterns: [
      /DesignTokens\.stories\.tsx/,
      /color palette|neutral|accent|semantic tokens/i,
      /typography|font-size|heading|type scale/i,
      /spacing|space-|gap|padding/i,
    ],
    forbiddenPatterns: [
      /\.storybook\/main\.ts/,
      /\.storybook\/preview\.ts/,
      /storybook\s+dev/,
      /@storybook\/react-vite/,
    ],
  },
] as const;

const STORYBOOK_CONFIG_PATTERNS = [
  /\.storybook\/main\.ts/,
  /\.storybook\/preview\.ts/,
  /package\.json/,
  /@storybook\/react-vite/,
  /storybook\s+dev/,
] as const;

const DESIGN_TOKEN_STORY_PATTERNS = [
  /DesignTokens\.stories\.tsx/,
  /color palette|neutral|accent|semantic tokens/i,
  /typography|font-size|heading|type scale/i,
  /spacing|space-|gap|padding/i,
] as const;

function testPath(filename: string): string {
  return resolve(TEST_DIR, filename);
}

function readSource(path: string): string {
  return existsSync(path) ? readFileSync(path, "utf-8") : "";
}

function matchingLabels(source: string, patterns: readonly RegExp[]): string[] {
  return patterns
    .filter((pattern) => pattern.test(source))
    .map((pattern) => pattern.source);
}

describe("storybook setup ownership governance boundary", () => {
  it("requires separate behavior-named owners with governance metadata", () => {
    const ownerGaps = REQUIRED_OWNER_SUITES.flatMap((suite) => {
      const path = testPath(suite.filename);
      const source = readSource(path);

      if (source.length === 0) {
        return [`${suite.filename}: missing owner for ${suite.scope}`];
      }

      const missingMetadata = REQUIRED_METADATA.filter(
        (metadata) => !source.includes(metadata),
      ).map((metadata) => `${suite.filename}: missing ${metadata}`);
      const missingScope = suite.requiredPatterns
        .filter((pattern) => !pattern.test(source))
        .map((pattern) => `${suite.filename}: missing ${pattern.source}`);
      const forbiddenScope = suite.forbiddenPatterns
        .filter((pattern) => pattern.test(source))
        .map((pattern) => `${suite.filename}: forbidden ${pattern.source}`);

      return [...missingMetadata, ...missingScope, ...forbiddenScope];
    });

    expect(
      ownerGaps,
      "Storybook config/tooling and DesignTokens story checks need separate package UI owners",
    ).toEqual([]);
  });

  it("keeps the legacy setup suite from owning both Storybook config and DesignTokens story checks", () => {
    const source = readSource(LEGACY_SETUP_SUITE);

    if (source.length === 0) {
      return;
    }

    const storybookConfigMatches = matchingLabels(
      source,
      STORYBOOK_CONFIG_PATTERNS,
    );
    const designTokenStoryMatches = matchingLabels(
      source,
      DESIGN_TOKEN_STORY_PATTERNS,
    );

    const violations =
      storybookConfigMatches.length > 0 && designTokenStoryMatches.length > 0
        ? [
            `storybookSetup.test.ts mixes config/tooling (${storybookConfigMatches.join(
              ", ",
            )}) with DesignTokens story checks (${designTokenStoryMatches.join(
              ", ",
            )})`,
          ]
        : [];

    expect(violations).toEqual([]);
  });

  it("prevents stale GUI path comments in package UI story tests", () => {
    const stalePathComments = readdirSync(TEST_DIR)
      .filter((filename) => /\.test\.tsx?$/.test(filename))
      .flatMap((filename) => {
        const source = readSource(testPath(filename));
        const comments = [
          ...source.matchAll(/\/\/[^\n]*|\/\*[\s\S]*?\*\//g),
        ].map((match) => match[0]);

        return comments
          .filter((comment) => /relative to apps\/gui/i.test(comment))
          .map((comment) => `${filename}: ${comment.trim()}`);
      });

    expect(
      stalePathComments,
      "package UI story test comments should describe packages/ui paths, not GUI app paths",
    ).toEqual([]);
  });
});
