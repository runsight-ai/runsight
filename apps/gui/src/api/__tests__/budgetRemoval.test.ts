/**
 * Settings API budget facade removal coverage.
 *
 * settingsApi must NOT export getBudgets, createBudget, updateBudget, or
 * deleteBudget after the dead facade is removed.
 */

import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const settingsSource = readFileSync(new URL("../settings.ts", import.meta.url), "utf8");

describe("budget facade removal — settings API", () => {
  it("does not export getBudgets from settingsApi", () => {
    expect(settingsSource).not.toMatch(/\bgetBudgets\b/);
  });

  it("does not export createBudget from settingsApi", () => {
    expect(settingsSource).not.toMatch(/\bcreateBudget\b/);
  });

  it("does not export updateBudget from settingsApi", () => {
    expect(settingsSource).not.toMatch(/\bupdateBudget\b/);
  });

  it("does not export deleteBudget from settingsApi", () => {
    expect(settingsSource).not.toMatch(/\bdeleteBudget\b/);
  });

  it("does not import SettingsBudgetListResponseSchema or SettingsBudgetResponseSchema", () => {
    expect(settingsSource).not.toMatch(/\bSettingsBudgetListResponseSchema\b/);
    expect(settingsSource).not.toMatch(/\bSettingsBudgetResponseSchema\b/);
  });
});
