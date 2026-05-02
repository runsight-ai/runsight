/**
 * Governance: generic block round-trip suite ownership split.
 *
 * Owner: GUI Surface YAML parser/compiler contracts.
 * Boundary: parser generic block behavior, compiler generic block behavior,
 * full round-trip behavior, workflow special cases, and known-type regression
 * smoke coverage live in behavior-owned suites instead of one catch-all file.
 * Shared YAML/node/edge builders belong in package-local GUI surface test
 * helpers, not inside the legacy round-trip suite.
 * Exit criteria: remove this source-inspection guard once the split suites and
 * helper module exist and ordinary behavior tests enforce those ownership
 * boundaries directly.
 */

import { existsSync, readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const SURFACE_TEST_DIR = __dirname;
const SURFACE_HELPERS_DIR = resolve(SURFACE_TEST_DIR, "helpers");
const LEGACY_ROUND_TRIP_SUITE = resolve(
  SURFACE_TEST_DIR,
  "genericBlockRoundTrip.test.ts",
);

const REQUIRED_OWNER_SUITES = [
  {
    name: "parser generic block contract",
    path: resolve(SURFACE_TEST_DIR, "genericBlockParserContract.test.ts"),
    requiredPattern: /describe\("Parser:/,
  },
  {
    name: "compiler generic block contract",
    path: resolve(SURFACE_TEST_DIR, "genericBlockCompilerContract.test.ts"),
    requiredPattern: /describe\("Compiler:/,
  },
  {
    name: "generic block round-trip contract",
    path: resolve(SURFACE_TEST_DIR, "genericBlockRoundTripContract.test.ts"),
    requiredPattern: /describe\("(?:Full round-trip|Mixed known \+ unknown types round-trip|Empty block round-trip|Nested objects:)/,
  },
  {
    name: "workflow special-case contract",
    path: resolve(SURFACE_TEST_DIR, "genericBlockWorkflowSpecialCase.test.ts"),
    requiredPattern: /describe\("Workflow special case preserved"/,
  },
  {
    name: "known-type regression smoke",
    path: resolve(SURFACE_TEST_DIR, "genericBlockKnownTypeRegression.test.ts"),
    requiredPattern: /describe\("(?:Known nested object fields still work|Existing known types unaffected)/,
  },
];

const BEHAVIOR_BUCKETS = [
  {
    name: "parser generic block contract",
    pattern: /describe\("Parser:/,
  },
  {
    name: "compiler generic block contract",
    pattern: /describe\("Compiler:/,
  },
  {
    name: "generic block round-trip contract",
    pattern: /describe\("(?:Full round-trip|Mixed known \+ unknown types round-trip|Empty block round-trip|Nested objects:)/,
  },
  {
    name: "workflow special-case contract",
    pattern: /describe\("Workflow special case preserved"/,
  },
  {
    name: "known-type regression smoke",
    pattern: /describe\("(?:Known nested object fields still work|Existing known types unaffected)/,
  },
];

const INLINE_SHARED_HELPERS = [
  {
    name: "makeYaml",
    pattern: /function\s+makeYaml\s*\(/,
  },
  {
    name: "mockNode",
    pattern: /function\s+mockNode\s*\(/,
  },
  {
    name: "mockEdge",
    pattern: /function\s+mockEdge\s*\(/,
  },
  {
    name: "compileOne",
    pattern: /function\s+compileOne\s*\(/,
  },
  {
    name: "roundTrip",
    pattern: /function\s+roundTrip\s*\(/,
  },
];

const REQUIRED_SHARED_HELPERS = [
  {
    name: "makeYaml",
    pattern: /export\s+function\s+makeYaml\s*\(/,
  },
  {
    name: "mockNode",
    pattern: /export\s+function\s+mockNode\s*\(/,
  },
  {
    name: "mockEdge",
    pattern: /export\s+function\s+mockEdge\s*\(/,
  },
  {
    name: "compileOne",
    pattern: /export\s+function\s+compileOne\s*\(/,
  },
  {
    name: "roundTrip",
    pattern: /export\s+function\s+roundTrip\s*\(/,
  },
];

function readLegacyRoundTripSuite(): string {
  if (!existsSync(LEGACY_ROUND_TRIP_SUITE)) {
    return "";
  }

  return readFileSync(LEGACY_ROUND_TRIP_SUITE, "utf-8");
}

function exportedHelperSources(): string[] {
  if (!existsSync(SURFACE_HELPERS_DIR)) {
    return [];
  }

  return readdirSync(SURFACE_HELPERS_DIR)
    .filter((fileName) => /\.[cm]?tsx?$/.test(fileName))
    .map((fileName) => readFileSync(resolve(SURFACE_HELPERS_DIR, fileName), "utf-8"));
}

describe("Governance: generic block round-trip suite ownership split", () => {
  it("requires each final behavior owner suite and the shared surface builder helper before the legacy suite can be removed", () => {
    const missingOwnerSuites = REQUIRED_OWNER_SUITES.filter(({ path }) => !existsSync(path))
      .map(({ name, path }) => `${name}: ${path}`);
    const ownerSuitesWithoutExpectedContract = REQUIRED_OWNER_SUITES
      .filter(({ path }) => existsSync(path))
      .filter(({ path, requiredPattern }) => !requiredPattern.test(readFileSync(path, "utf-8")))
      .map(({ name, path }) => `${name}: ${path}`);
    const helperSources = exportedHelperSources();
    const missingSharedHelpers = REQUIRED_SHARED_HELPERS
      .filter(({ pattern }) => !helperSources.some((source) => pattern.test(source)))
      .map(({ name }) => name);

    expect({
      missingOwnerSuites,
      ownerSuitesWithoutExpectedContract,
      missingSharedHelpers,
    }).toEqual({
      missingOwnerSuites: [],
      ownerSuitesWithoutExpectedContract: [],
      missingSharedHelpers: [],
    });
  });

  it("keeps the legacy round-trip suite from owning multiple behavior contracts and shared builders", () => {
    const source = readLegacyRoundTripSuite();

    if (source.length === 0) {
      return;
    }

    const presentBehaviorBuckets = BEHAVIOR_BUCKETS.filter(({ pattern }) =>
      pattern.test(source),
    ).map(({ name }) => name);
    const inlineSharedHelpers = INLINE_SHARED_HELPERS.filter(({ pattern }) =>
      pattern.test(source),
    ).map(({ name }) => name);

    const violations = [
      presentBehaviorBuckets.length > 1
        ? `split behavior owners instead of mixing: ${presentBehaviorBuckets.join(", ")}`
        : null,
      inlineSharedHelpers.length > 0
        ? `move shared YAML/node/edge builders to __tests__/helpers: ${inlineSharedHelpers.join(", ")}`
        : null,
    ].filter((violation): violation is string => violation !== null);

    expect(violations).toEqual([]);
  });
});
