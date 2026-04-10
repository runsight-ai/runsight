/**
 * RUN-742: Reduce Playwright skip-driven coverage loss
 *
 * Source-reading audit that asserts the Playwright spec files meet the
 * skip-reduction targets defined in the acceptance criteria:
 *
 *   AC1: Total test.skip() sites ≤ 31 (currently 63)
 *   AC2: No files use "previous test" cascade skip messages (currently 6 files)
 *   AC3: Key files use beforeAll for setup, not previous-test state
 *   AC4: Conditional variable-cascade skips are eliminated (test.skip(!someId, ...))
 *
 * These tests INTENTIONALLY FAIL on the current codebase — they are the
 * Red Team tests for the cleanup sprint.
 *
 * Run:
 *   cd apps/gui && npx vitest run src/features/e2e-audit/__tests__/run742-skip-reduction.test.ts --reporter=verbose
 */

import { describe, it, expect } from "vitest";
import { readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SPECS_DIR = resolve(
  __dirname,
  "../../../../../../testing/gui-e2e/tests",
);

function getSpecFiles(): string[] {
  return readdirSync(SPECS_DIR)
    .filter((f) => f.endsWith(".spec.ts"))
    .map((f) => resolve(SPECS_DIR, f));
}

interface FileContent {
  name: string;
  path: string;
  source: string;
}

function readAllSpecs(): FileContent[] {
  return getSpecFiles().map((filePath) => ({
    name: filePath.split("/").pop()!,
    path: filePath,
    source: readFileSync(filePath, "utf-8"),
  }));
}

function countOccurrences(source: string, pattern: RegExp): number {
  return (source.match(pattern) ?? []).length;
}

// ---------------------------------------------------------------------------
// AC1: Total test.skip() count across all spec files must be ≤ 31
//
// Current state: 63 occurrences — the target halves it.
// ---------------------------------------------------------------------------

describe("AC1 — total test.skip() count ≤ 31", () => {
  it("counts all test.skip( calls and asserts the target is met", () => {
    const specs = readAllSpecs();

    const breakdown: { file: string; count: number }[] = [];
    let total = 0;

    for (const spec of specs) {
      const count = countOccurrences(spec.source, /test\.skip\(/g);
      if (count > 0) {
        breakdown.push({ file: spec.name, count });
        total += count;
      }
    }

    // Print breakdown on failure for easy diagnosis
    const report = breakdown
      .sort((a, b) => b.count - a.count)
      .map((r) => `  ${r.file}: ${r.count}`)
      .join("\n");

    expect(
      total,
      `Total test.skip() count is ${total} — must be ≤ 31.\n\nBreakdown:\n${report}`,
    ).toBeLessThanOrEqual(31);
  });
});

// ---------------------------------------------------------------------------
// AC2: No files should use the "previous test" cascade skip message pattern.
//
// Pattern: test.skip(!<variable>, "... was not created in previous test")
// This phrase explicitly documents the cascade dependency and must be removed.
// Current state: 6 files contain this phrase.
// ---------------------------------------------------------------------------

describe("AC2 — no 'previous test' cascade skip messages", () => {
  it("finds zero spec files referencing 'previous test' in a skip message", () => {
    const specs = readAllSpecs();

    const offenders = specs.filter((spec) =>
      spec.source.includes("in previous test"),
    );

    const fileList = offenders.map((s) => `  ${s.name}`).join("\n");

    expect(
      offenders.length,
      `${offenders.length} file(s) still use "in previous test" cascade skip messages:\n${fileList}\n\n` +
        `These skips must be replaced with beforeAll fixtures so each test is self-contained.`,
    ).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// AC3a: workflows-crud.spec.ts must use beforeAll for setup
//
// Current state: the file sets createdWorkflowId inside the "create workflow"
// test body, so later tests cascade-skip if that test fails.
// ---------------------------------------------------------------------------

describe("AC3 — key files use beforeAll for test data setup", () => {
  it("workflows-crud.spec.ts has a beforeAll that creates test data", () => {
    const spec = readAllSpecs().find((s) => s.name === "workflows-crud.spec.ts");
    expect(spec, "workflows-crud.spec.ts not found in spec directory").toBeDefined();

    const source = spec!.source;

    // Must have a beforeAll block
    const hasBeforeAll = /test\.beforeAll\s*\(/.test(source);
    expect(
      hasBeforeAll,
      "workflows-crud.spec.ts must have a test.beforeAll() that creates the workflow via API, " +
        "so downstream tests are not dependent on the 'create workflow' test passing.",
    ).toBe(true);

    // The beforeAll must contain an API POST to /workflows (fixture-style creation)
    const beforeAllBlock = source.match(
      /test\.beforeAll\s*\([\s\S]*?^\s*\}\s*\)\s*;/m,
    )?.[0] ?? "";

    const fixtureCreatesViaApi =
      /fetch\(.*\/workflows.*POST/s.test(beforeAllBlock) ||
      /method.*POST[\s\S]*?\/workflows/s.test(beforeAllBlock) ||
      // Accept any beforeAll that does a POST (may use a helper)
      /POST/.test(beforeAllBlock);

    expect(
      fixtureCreatesViaApi,
      "The beforeAll in workflows-crud.spec.ts must create a workflow via POST to the API, " +
        "not rely on a previous test having done so.",
    ).toBe(true);
  });

  it("canvas-mutations.spec.ts has a beforeAll that creates test data", () => {
    const spec = readAllSpecs().find((s) => s.name === "canvas-mutations.spec.ts");
    expect(spec, "canvas-mutations.spec.ts not found in spec directory").toBeDefined();

    const source = spec!.source;

    const hasBeforeAll = /test\.beforeAll\s*\(/.test(source);
    expect(
      hasBeforeAll,
      "canvas-mutations.spec.ts must have a test.beforeAll() that creates the workflow via API.",
    ).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// AC3b: CRUD files that still lack beforeAll must be identified.
//
// The remaining CRUD browser specs should use beforeAll fixtures instead of
// previous-test chains. Retired tasks/steps browser specs are intentionally gone.
// ---------------------------------------------------------------------------

describe("AC3b — CRUD spec files must use beforeAll, not previous-test chains", () => {
  const CRUD_FILES_REQUIRING_BEFORE_ALL = [
    "souls-crud.spec.ts",
    "workflows-crud.spec.ts",
    "settings-providers.spec.ts",
  ];

  for (const fileName of CRUD_FILES_REQUIRING_BEFORE_ALL) {
    it(`${fileName} uses test.beforeAll() for entity creation`, () => {
      const spec = readAllSpecs().find((s) => s.name === fileName);
      expect(spec, `${fileName} not found in spec directory`).toBeDefined();

      const hasBeforeAll = /test\.beforeAll\s*\(/.test(spec!.source);
      expect(
        hasBeforeAll,
        `${fileName} must use test.beforeAll() to create test data via API ` +
          `instead of letting a previous test set state. ` +
          `Currently it uses cascade test.skip(!createdId, "... not created in previous test").`,
      ).toBe(true);
    });
  }
});

// ---------------------------------------------------------------------------
// AC4: Variable-cascade skips — test.skip(!<id>, ...) — must be eliminated.
//
// These are skips where the condition is the falsy check of a variable that
// was supposed to be set by a previous test in the same describe block.
// Examples: test.skip(!createdWorkflowId, ...), test.skip(!createdSoulId, ...)
//
// After the fix, any remaining test.skip(!variable) patterns should only
// reference variables populated in a beforeAll fixture (not previous tests).
// The count of files with these patterns must drop to 0.
// ---------------------------------------------------------------------------

describe("AC4 — variable-cascade test.skip(!id) patterns eliminated", () => {
  it("no spec files contain test.skip(!<variable>) patterns outside of beforeAll-backed files", () => {
    const specs = readAllSpecs();

    // These are the files that have cascade skips but NO beforeAll
    // (i.e. the variable can only have been set by a previous test).
    const cascadeWithoutBeforeAll = specs.filter((spec) => {
      const hasCascadeSkip = /test\.skip\(!\w+/.test(spec.source);
      const hasBeforeAll = /test\.beforeAll\s*\(/.test(spec.source);
      // A cascade without beforeAll is the bad pattern
      return hasCascadeSkip && !hasBeforeAll;
    });

    const fileList = cascadeWithoutBeforeAll
      .map(
        (s) =>
          `  ${s.name} (${countOccurrences(s.source, /test\.skip\(!\w+/g)} cascade skip(s))`,
      )
      .join("\n");

    expect(
      cascadeWithoutBeforeAll.length,
      `${cascadeWithoutBeforeAll.length} file(s) use test.skip(!variable) cascades without a beforeAll fixture:\n` +
        `${fileList}\n\n` +
        `These files must be converted: add a beforeAll that creates the entity via API ` +
        `so individual test failures don't cascade-skip the rest of the file.`,
    ).toBe(0);
  });

  it("total count of test.skip(!variable) patterns across all files is ≤ 10", () => {
    const specs = readAllSpecs();

    const breakdown: { file: string; count: number }[] = [];
    let total = 0;

    for (const spec of specs) {
      const count = countOccurrences(spec.source, /test\.skip\(!\w+/g);
      if (count > 0) {
        breakdown.push({ file: spec.name, count });
        total += count;
      }
    }

    const report = breakdown
      .sort((a, b) => b.count - a.count)
      .map((r) => `  ${r.file}: ${r.count} cascade skip(s)`)
      .join("\n");

    expect(
      total,
      `Total test.skip(!variable) cascade count is ${total} — target is ≤ 10.\n\nBreakdown:\n${report}`,
    ).toBeLessThanOrEqual(10);
  });
});
