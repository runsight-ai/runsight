/**
 * Governance coverage for onboarding E2E marker cleanup.
 *
 * This E2E-owned suite protects onboarding browser flows from being hidden
 * behind permanent expected-failure markers. Delete this governance suite once
 * marker policy is enforced by lint rules inside testing/gui-e2e.
 */

import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const ONBOARDING_SPEC = resolve(__dirname, "../onboarding.spec.ts");

function readOnboardingSpec(): string {
  return readFileSync(ONBOARDING_SPEC, "utf-8");
}

describe("Playwright onboarding marker governance", () => {
  it("keeps onboarding journeys free of permanent expected-failure markers", () => {
    const source = readOnboardingSpec();
    const occurrences = (source.match(/test\.fail\s*\(\s*true/g) ?? []).length;

    expect(
      occurrences,
      `onboarding.spec.ts has ${occurrences} test.fail(true, ...) marker(s).`,
    ).toBe(0);
  });

  it("keeps the blank-canvas onboarding journey active", () => {
    const source = readOnboardingSpec();

    expect(source).toMatch(/blank-canvas onboarding/);
  });

  it("keeps the provider-present onboarding journey active", () => {
    const source = readOnboardingSpec();

    expect(source).toMatch(/provider-present onboarding/);
  });
});
