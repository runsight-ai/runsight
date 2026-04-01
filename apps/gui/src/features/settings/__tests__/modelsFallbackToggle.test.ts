import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const SRC_DIR = resolve(__dirname, "../../..");

function readSource(relativePath: string): string {
  return readFileSync(resolve(SRC_DIR, relativePath), "utf-8");
}

const MODELS_TAB_PATH = "features/settings/ModelsTab.tsx";
const SETTINGS_QUERIES_PATH = "queries/settings.ts";
const SETTINGS_API_PATH = "api/settings.ts";

describe("ModelsTab fallback chain toggle wiring", () => {
  it("imports Switch plus app-settings hooks for fallback toggle state", () => {
    const source = readSource(MODELS_TAB_PATH);
    expect(source).toMatch(/import.*Switch.*from.*@runsight\/ui\/switch/);
    expect(source).toMatch(/useAppSettings/);
    expect(source).toMatch(/useUpdateAppSettings/);
  });

  it("renders a Switch next to the Fallback Chain heading", () => {
    const source = readSource(MODELS_TAB_PATH);
    expect(source).toMatch(/Fallback Chain/);
    expect(source).toMatch(/<Switch\b/);
  });

  it("reads fallback_chain_enabled from app settings so the toggle survives refresh", () => {
    const source = readSource(MODELS_TAB_PATH);
    expect(source).toMatch(/fallback_chain_enabled/);
    expect(source).toMatch(/useAppSettings\(\)/);
    expect(source).toMatch(/fallback_chain_enabled\s*\?\?+\s*true|fallbackChainEnabled.*=\s*.*fallback_chain_enabled.*\?\?\s*true/);
  });

  it("persists toggle changes through useUpdateAppSettings", () => {
    const source = readSource(MODELS_TAB_PATH);
    expect(source).toMatch(/updateAppSettings/);
    expect(source).toMatch(/onCheckedChange=\{.*fallback_chain_enabled:\s*\w+/s);
    expect(source).toMatch(/mutateAsync?\s*\(\s*\{\s*fallback_chain_enabled:/);
  });
});

describe("Fallback chain disabled state", () => {
  it("passes the enabled flag into FallbackChainSection", () => {
    const source = readSource(MODELS_TAB_PATH);
    expect(source).toMatch(/<FallbackChainSection\b/);
    expect(source).toMatch(/enabled=\{fallbackChainEnabled\}/);
  });

  it("greys out the fallback chain list when the toggle is off", () => {
    const source = readSource(MODELS_TAB_PATH);
    expect(source).toMatch(/opacity-50|grayscale|text-muted/);
    expect(source).toMatch(/enabled.*\?/s);
  });

  it("disables reorder controls when the toggle is off and restores them when enabled", () => {
    const source = readSource(MODELS_TAB_PATH);
    expect(source).toMatch(/disabled=\{!enabled\s*\|\|/);
    expect(source).toMatch(/disabled=\{!enabled\s*\|\|\s*i === 0\}/);
    expect(source).toMatch(/disabled=\{!enabled\s*\|\|\s*i === localChain\.length - 1\}/);
  });

  it("guards reorder actions behind the enabled state", () => {
    const source = readSource(MODELS_TAB_PATH);
    expect(source).toMatch(/if\s*\(\s*!enabled\s*\)\s*return/);
  });
});

describe("Fallback chain persistence contracts", () => {
  it("keeps app settings query/mutation hooks available for settings screens", () => {
    const source = readSource(SETTINGS_QUERIES_PATH);
    expect(source).toMatch(/export function useAppSettings/);
    expect(source).toMatch(/export function useUpdateAppSettings/);
  });

  it("declares fallback_chain_enabled in the app settings API schema", () => {
    const source = readSource(SETTINGS_API_PATH);
    expect(source).toMatch(/AppSettingsOutSchema/);
    expect(source).toMatch(/from\s+"@runsight\/shared\/zod"/);
    expect(source).toMatch(/return AppSettingsOutSchema\.parse\(res\);/);
  });
});
