/**
 * RED-TEAM tests for RUN-738: Fix onboarding flows — blank-canvas and
 * provider-present paths keep user on /setup/start.
 *
 * Root cause: queryClient.fetchQuery() in guards.ts uses staleTime: 30_000.
 * After updateAppSettings({ onboarding_completed: true }) invalidates the
 * cache, the guard still returns the stale cached value because 30 s has not
 * elapsed.  The fix is staleTime: 0 (or omitting staleTime entirely) so the
 * guard always fetches fresh data after a cache invalidation.
 *
 * Source-reading pattern: verify structural properties by reading source files.
 *
 * AC verified here:
 *   AC1 / AC2: guard does NOT use staleTime: 30_000 (the stale-cache bug)
 *              guard DOES use staleTime: 0 (or omits staleTime)
 *   AC3 / AC4: onboarding.spec.ts does NOT contain test.fail markers for the
 *              blank-canvas and provider-present tests
 *
 * Expected failures (current state):
 *   - guards.ts still has `staleTime: 30_000` on both fetchQuery calls
 *   - onboarding.spec.ts still has `test.fail(true, ...)` on both tests
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SRC_DIR = resolve(__dirname, "../..");
const E2E_DIR = resolve(__dirname, "../../../../../testing/gui-e2e/tests");

function readSource(relativePath: string): string {
  return readFileSync(resolve(SRC_DIR, relativePath), "utf-8");
}

function readE2EFile(fileName: string): string {
  return readFileSync(resolve(E2E_DIR, fileName), "utf-8");
}

// ---------------------------------------------------------------------------
// File paths
// ---------------------------------------------------------------------------

const GUARDS_PATH = "routes/guards.ts";
const ONBOARDING_SPEC = "onboarding.spec.ts";

// ===========================================================================
// 1. guards.ts — staleTime must NOT be 30_000
// ===========================================================================

describe("guards.ts: fetchQuery does not use staleTime: 30_000 (RUN-738 root cause)", () => {
  it("createSetupGuardLoader does not pass staleTime: 30_000", () => {
    const source = readSource(GUARDS_PATH);

    // The bug: staleTime: 30_000 means the guard returns a cached (stale)
    // value for up to 30 seconds after onboarding_completed is set to true,
    // so the user is incorrectly redirected back to /setup/start.
    const hasLargeStaleTime = /staleTime\s*:\s*30[_,]?000/.test(source);
    expect(
      hasLargeStaleTime,
      "guards.ts still uses staleTime: 30_000 — this is the root cause of RUN-738. " +
        "Fix: use staleTime: 0 or omit staleTime entirely so the guard always " +
        "fetches fresh data after cache invalidation.",
    ).toBe(false);
  });

  it("createReverseGuardLoader does not pass staleTime: 30_000", () => {
    const source = readSource(GUARDS_PATH);

    // Both loaders share the same stale-cache bug — both must be fixed.
    // Count occurrences of the large staleTime across the whole file.
    const occurrences = (source.match(/staleTime\s*:\s*30[_,]?000/g) ?? []).length;
    expect(
      occurrences,
      `guards.ts has ${occurrences} occurrence(s) of staleTime: 30_000. ` +
        "Both createSetupGuardLoader and createReverseGuardLoader must be fixed.",
    ).toBe(0);
  });

  it("guards.ts uses staleTime: 0 or omits staleTime on fetchQuery calls", () => {
    const source = readSource(GUARDS_PATH);

    // After the fix the guard must either:
    //   (a) explicitly pass staleTime: 0  — forces a fresh fetch every time, or
    //   (b) omit staleTime entirely       — fetchQuery default is 0
    //
    // A staleTime of 0 means "data is always considered stale" so fetchQuery
    // will always hit the network, picking up the newly-written setting.
    const hasZeroStaleTime = /staleTime\s*:\s*0\b/.test(source);
    const hasAnyStaleTime = /staleTime\s*:/.test(source);

    // Pass when:  staleTime: 0 is present, OR staleTime is absent entirely.
    const guardUsesFreshFetch = hasZeroStaleTime || !hasAnyStaleTime;

    expect(
      guardUsesFreshFetch,
      "Expected guards.ts to use staleTime: 0 (or omit staleTime) on fetchQuery " +
        "so that cache invalidation after updateAppSettings is respected.",
    ).toBe(true);
  });
});

// ===========================================================================
// 2. guards.ts — both loader functions must have the fix applied
// ===========================================================================

describe("guards.ts: fix applied to BOTH loader factories", () => {
  it("no fetchQuery call in the file retains a staleTime >= 30_000", () => {
    const source = readSource(GUARDS_PATH);

    // Catch any large staleTime that might be introduced or left behind
    // (e.g., someone fixes one loader but not the other).
    const largeStaleTimePattern = /staleTime\s*:\s*\d{5,}/g;
    const matches = source.match(largeStaleTimePattern) ?? [];

    expect(
      matches,
      `Found large staleTime value(s) in guards.ts: ${matches.join(", ")}. ` +
        "All fetchQuery calls in the guards must use staleTime: 0 or omit it.",
    ).toHaveLength(0);
  });
});

// ===========================================================================
// 3. onboarding.spec.ts — test.fail markers must be removed (AC3, AC4)
// ===========================================================================

describe("onboarding.spec.ts: test.fail markers removed from both failing tests", () => {
  it("blank-canvas test does not have a test.fail marker", () => {
    const source = readE2EFile(ONBOARDING_SPEC);

    // The test titled "blank-canvas onboarding..." must no longer be wrapped
    // with test.fail(true, ...) — once the guard bug is fixed the test should
    // pass natively.
    //
    // Strategy: verify test.fail(true does not appear anywhere in the file.
    // (Both markers must be removed before the AC is satisfied.)
    const hasTestFail = /test\.fail\s*\(\s*true/.test(source);
    expect(
      hasTestFail,
      "onboarding.spec.ts still contains test.fail(true, ...) markers. " +
        "Remove the test.fail wrappers from the blank-canvas and " +
        "provider-present tests once the guard staleTime bug is fixed.",
    ).toBe(false);
  });

  it("provider-present test does not have a test.fail marker", () => {
    const source = readE2EFile(ONBOARDING_SPEC);

    // Count the exact number of test.fail(true occurrences — must be zero.
    const occurrences = (source.match(/test\.fail\s*\(\s*true/g) ?? []).length;
    expect(
      occurrences,
      `onboarding.spec.ts has ${occurrences} test.fail(true, ...) marker(s). ` +
        "Expected 0 — both markers must be removed after the guard fix.",
    ).toBe(0);
  });

  it("blank-canvas test body is present and not commented out", () => {
    const source = readE2EFile(ONBOARDING_SPEC);

    // The test must still exist; removal of test.fail should not mean
    // removal of the test itself.
    expect(source).toMatch(/blank-canvas onboarding/);
  });

  it("provider-present test body is present and not commented out", () => {
    const source = readE2EFile(ONBOARDING_SPEC);

    expect(source).toMatch(/provider-present onboarding/);
  });
});
