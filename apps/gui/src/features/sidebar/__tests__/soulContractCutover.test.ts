import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const FEATURE_DIR = resolve(__dirname, "..");
const MODALS_SOURCE = readFileSync(resolve(FEATURE_DIR, "SoulModals.tsx"), "utf-8");
const LIST_SOURCE = readFileSync(resolve(FEATURE_DIR, "SoulList.tsx"), "utf-8");

describe("RUN-440 soul sidebar contract cutover", () => {
  it("NewSoulModal submits role and model_name instead of name/models", () => {
    expect(MODALS_SOURCE).toMatch(/role:\s*name\.trim\(\)/);
    expect(MODALS_SOURCE).toMatch(/model_name:\s*selectedModels/);
    expect(MODALS_SOURCE).not.toMatch(/name:\s*name\.trim\(\)/);
    expect(MODALS_SOURCE).not.toMatch(/models:\s*selectedModels/);
  });

  it("EditSoulModal reads and writes role/model_name", () => {
    expect(MODALS_SOURCE).toMatch(/setName\(soul\.role\s*\|\|\s*""\)/);
    expect(MODALS_SOURCE).toMatch(/setSelectedModels\(soul\.model_name\s*\?/);
    expect(MODALS_SOURCE).toMatch(/role:\s*name\.trim\(\)\s*\|\|\s*null/);
    expect(MODALS_SOURCE).toMatch(/model_name:\s*selectedModels/);
    expect(MODALS_SOURCE).not.toMatch(/setName\(soul\.name/);
    expect(MODALS_SOURCE).not.toMatch(/soul\.models/);
  });

  it("SoulList renders and searches by role with model_name column data", () => {
    expect(LIST_SOURCE).toMatch(/key:\s*"role"/);
    expect(LIST_SOURCE).toMatch(/soul\.role\s*\|\|\s*"Unnamed Soul"/);
    expect(LIST_SOURCE).toMatch(/key:\s*"model_name"/);
    expect(LIST_SOURCE).toMatch(/const modelName = soul\.model_name/);
    expect(LIST_SOURCE).toMatch(/searchKeys:\s*\["role",\s*"system_prompt"\]/);
    expect(LIST_SOURCE).toMatch(/getItemName:\s*\(soul\)\s*=>\s*soul\.role\s*\|\|\s*"Unnamed Soul"/);
    expect(LIST_SOURCE).not.toMatch(/soul\.name/);
    expect(LIST_SOURCE).not.toMatch(/soul\.models/);
  });
});
