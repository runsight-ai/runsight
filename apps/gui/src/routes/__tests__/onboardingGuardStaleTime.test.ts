/**
 * Guard freshness coverage for onboarding route loaders.
 *
 * This GUI-owned suite only inspects route guard source. Browser-flow marker
 * governance lives in the E2E workspace.
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SRC_DIR = resolve(__dirname, "../..");

function readSource(relativePath: string): string {
  return readFileSync(resolve(SRC_DIR, relativePath), "utf-8");
}

// ---------------------------------------------------------------------------
// File paths
// ---------------------------------------------------------------------------

const GUARDS_PATH = "routes/guards.ts";

// ===========================================================================
// 1. guards.ts - staleTime must NOT be 30_000
// ===========================================================================

describe("onboarding guard fetch freshness", () => {
  it("createSetupGuardLoader does not pass staleTime: 30_000", () => {
    const source = readSource(GUARDS_PATH);

    // staleTime: 30_000 means the guard returns a cached value
    // value for up to 30 seconds after onboarding_completed is set to true,
    // so the user is incorrectly redirected back to /setup/start.
    const hasLargeStaleTime = /staleTime\s*:\s*30[_,]?000/.test(source);
    expect(
      hasLargeStaleTime,
      "guards.ts still uses staleTime: 30_000. " +
        "Use staleTime: 0 or omit staleTime entirely so the guard always " +
        "fetches fresh data after cache invalidation.",
    ).toBe(false);
  });

  it("createReverseGuardLoader does not pass staleTime: 30_000", () => {
    const source = readSource(GUARDS_PATH);

    // Both loaders share the same stale-cache risk and must stay fresh.
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
// 2. guards.ts - both loader functions must have the fix applied
// ===========================================================================

describe("onboarding guard loader consistency", () => {
  it("no fetchQuery call in the file retains a staleTime >= 30_000", () => {
    const source = readSource(GUARDS_PATH);

    // Catch any large staleTime that might be introduced in one loader.
    const largeStaleTimePattern = /staleTime\s*:\s*\d{5,}/g;
    const matches = source.match(largeStaleTimePattern) ?? [];

    expect(
      matches,
      `Found large staleTime value(s) in guards.ts: ${matches.join(", ")}. ` +
        "All fetchQuery calls in the guards must use staleTime: 0 or omit it.",
    ).toHaveLength(0);
  });
});
