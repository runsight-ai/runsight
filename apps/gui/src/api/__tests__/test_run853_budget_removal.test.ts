/**
 * Red tests for RUN-853: Remove budget facade from settings API.
 *
 * settingsApi must NOT export getBudgets, createBudget, updateBudget, or
 * deleteBudget after the dead facade is removed. These tests FAIL before Green.
 */

import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const settingsSource = readFileSync(new URL("../settings.ts", import.meta.url), "utf8");

describe("RUN-853 budget facade removal — settings API", () => {
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
