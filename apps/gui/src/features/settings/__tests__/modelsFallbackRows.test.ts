import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const SRC_DIR = resolve(__dirname, "../../..");

function readSource(relativePath: string): string {
  return readFileSync(resolve(SRC_DIR, relativePath), "utf-8");
}

const MODELS_TAB_PATH = "features/settings/ModelsTab.tsx";

describe("ModelsTab per-provider fallback row wiring", () => {
  it("fully deletes FallbackChainSection and all chain-only traces", () => {
    const source = readSource(MODELS_TAB_PATH);

    expect(source).not.toMatch(/FallbackChainSection/);
    expect(source).not.toMatch(/GripVertical/);
    expect(source).not.toMatch(/ChevronUp/);
    expect(source).not.toMatch(/ChevronDown/);
    expect(source).not.toMatch(/handleReorderChain/);
    expect(source).not.toMatch(/showFallbackChain/);
    expect(source).not.toMatch(/fallback_chain/);
    expect(source).not.toMatch(/Retry order when primary fails/);
    expect(source).not.toMatch(/Drag to reorder/);
  });

  it("declares private FallbackSection and FallbackTargetRow components", () => {
    const source = readSource(MODELS_TAB_PATH);

    expect(source).toMatch(/function\s+FallbackSection|const\s+FallbackSection\s*=\s*\(/);
    expect(source).toMatch(/function\s+FallbackTargetRow|const\s+FallbackTargetRow\s*=\s*\(/);
  });

  it("maps one fallback row per fallback target entry and passes row-specific props into FallbackTargetRow", () => {
    const source = readSource(MODELS_TAB_PATH);

    expect(source).toMatch(
      /fallbackTargets\.map\s*\(\s*\((fallbackTarget|row)\)\s*=>[\s\S]*<FallbackTargetRow\b/,
    );
    expect(source).toMatch(/<FallbackTargetRow[\s\S]*key=\{(fallbackTarget|row)\.id\}/);
    expect(source).toMatch(
      /<FallbackTargetRow[\s\S]*fallbackTarget=\{(fallbackTarget|row)\}/,
    );
    expect(source).toMatch(/<FallbackTargetRow[\s\S]*enabledSiblingProviders=\{/);
    expect(source).toMatch(/<FallbackTargetRow[\s\S]*onCommit=\{/);
    expect(source).toMatch(/<FallbackTargetRow[\s\S]*onClear=\{/);
  });

  it("bases fallback eligibility on enabled providers and excludes the row's own provider from sibling options", () => {
    const source = readSource(MODELS_TAB_PATH);

    expect(source).toMatch(/allProviders/);
    expect(source).toMatch(/enabledProviders/);
    expect(source).toMatch(/is_active\s*\?\?\s*true|provider\.is_active/);
    expect(source).toMatch(/enabledSiblingProviders/);
    expect(source).toMatch(
      /provider\.id\s*!==\s*model\.provider_id|provider\.id\s*!==\s*row\.provider_id|provider\.id\s*!==\s*providerId|provider\.id\s*!==\s*fallbackTarget\.provider_id/,
    );
  });

  it("populates the model select from the selected fallback provider's model list", () => {
    const source = readSource(MODELS_TAB_PATH);

    expect(source).toMatch(/selectedFallbackProvider/);
    expect(source).toMatch(/fallback provider/i);
    expect(source).toMatch(/models/);
    expect(source).toMatch(
      /selectedFallbackProvider.*models|fallbackProvider.*models|getProviderModels\(\s*selectedFallbackProvider/,
    );
  });

  it("resets the model when the fallback provider changes and does not mutate on provider selection alone", () => {
    const source = readSource(MODELS_TAB_PATH);

    expect(source).toMatch(/set.*FallbackProvider/);
    expect(source).toMatch(/set.*FallbackModel\(null\)|set.*FallbackModel\(""\)/);
    expect(source).toMatch(
      /if\s*\(\s*!.*fallbackProvider.*\|\|\s*!.*fallbackModel.*\)\s*return|if\s*\(\s*!.*fallbackModel.*\)\s*return/,
    );
  });

  it("commits only once both fallback provider and fallback model exist", () => {
    const source = readSource(MODELS_TAB_PATH);

    expect(source).toMatch(/updateFallbackTarget\.mutateAsync/);
    expect(source).toMatch(/fallback_provider_id/);
    expect(source).toMatch(/fallback_model_id/);
    expect(source).toMatch(
      /if\s*\(\s*!.*fallbackProvider.*\|\|\s*!.*fallbackModel.*\)\s*return|if\s*\(\s*!.*fallbackProviderId.*\|\|\s*!.*fallbackModelId.*\)\s*return/,
    );
  });

  it("clears a fallback mapping immediately by sending both fallback fields cleared together", () => {
    const source = readSource(MODELS_TAB_PATH);

    expect(source).toMatch(/Clear fallback/);
    expect(source).toMatch(/updateFallbackTarget\.mutateAsync/);
    expect(source).toMatch(/fallback_provider_id\s*:\s*["']{2}/);
    expect(source).toMatch(/fallback_model_id\s*:\s*["']{2}/);
    expect(source).toMatch(
      /updateFallbackTarget\.mutateAsync\([\s\S]*fallback_provider_id\s*:\s*["']{2}[\s\S]*fallback_model_id\s*:\s*["']{2}[\s\S]*\)/,
    );
  });
});
