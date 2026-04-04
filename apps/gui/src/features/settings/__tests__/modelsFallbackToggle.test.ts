import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const SRC_DIR = resolve(__dirname, "../../..");

function readSource(relativePath: string): string {
  return readFileSync(resolve(SRC_DIR, relativePath), "utf-8");
}

const MODELS_TAB_PATH = "features/settings/ModelsTab.tsx";
const SETTINGS_PAGE_PATH = "features/settings/SettingsPage.tsx";
const SETTINGS_QUERIES_PATH = "queries/settings.ts";
const SETTINGS_API_PATH = "api/settings.ts";

describe("ModelsTab fallback section wiring", () => {
  it("renders a dedicated fallback section without the old default-model section", () => {
    const source = readSource(MODELS_TAB_PATH);

    expect(source).toMatch(/Fallback/);
    expect(source).not.toMatch(/Default Model per Provider/);
  });

  it("keeps settings navigation scoped to Providers and Fallback tabs", () => {
    const source = readSource(SETTINGS_PAGE_PATH);

    expect(source).toMatch(/TabsTrigger value="providers">Providers<\/TabsTrigger>/);
    expect(source).toMatch(/TabsTrigger value="fallback">Fallback<\/TabsTrigger>/);
    expect(source).not.toMatch(/TabsTrigger value="models">/);
    expect(source).not.toMatch(/Default Model/);
  });

  it("imports Switch plus app-settings hooks for fallback toggle state", () => {
    const source = readSource(MODELS_TAB_PATH);

    expect(source).toMatch(/import.*Switch.*from.*@runsight\/ui\/switch/);
    expect(source).toMatch(/useAppSettings/);
    expect(source).toMatch(/useUpdateAppSettings/);
  });

  it("reads fallback_enabled from app settings so the toggle survives refresh", () => {
    const source = readSource(MODELS_TAB_PATH);

    expect(source).toMatch(/fallback_enabled/);
    expect(source).not.toMatch(/fallback_chain_enabled/);
    expect(source).toMatch(/useAppSettings\(\)/);
    expect(source).toMatch(
      /fallback_enabled\s*\?\?+\s*false|fallbackEnabled.*=\s*.*fallback_enabled.*\?\?\s*false/,
    );
  });

  it("keeps the full-page Models empty state keyed off all configured providers being absent", () => {
    const source = readSource(MODELS_TAB_PATH);

    expect(source).toMatch(/allProviders/);
    expect(source).toMatch(/allProviders\.length\s*===\s*0/);
    expect(source).toMatch(/No providers configured/);
  });

  it("renders a disabled fallback empty state when fewer than two providers are enabled", () => {
    const source = readSource(MODELS_TAB_PATH);

    expect(source).toMatch(/enabledProviders/);
    expect(source).toMatch(/canConfigureFallback\s*=\s*enabledProviders\.length\s*>=\s*2/);
    expect(source).toMatch(
      /Enable at least two providers to configure runtime fallback\. Once two providers are enabled, you can choose one fallback target per provider\./,
    );
    expect(source).toMatch(/disabled=\{[^}]*!canConfigureFallback/);
  });

  it("greys out fallback rows when the toggle is off and restores them when enabled", () => {
    const source = readSource(MODELS_TAB_PATH);

    expect(source).toMatch(/enabledProviders\.length\s*>=\s*2/);
    expect(source).toMatch(/opacity\s*:\s*0\.4/);
    expect(source).toMatch(/pointerEvents\s*:\s*["']none["']/);
  });

  it("persists toggle changes through useUpdateAppSettings with fallback_enabled", () => {
    const source = readSource(MODELS_TAB_PATH);

    expect(source).toMatch(/updateAppSettings/);
    expect(source).toMatch(/onCheckedChange=\{.*fallback_enabled:\s*\w+/s);
    expect(source).toMatch(/mutateAsync?\s*\(\s*\{\s*fallback_enabled:/);
    expect(source).not.toMatch(/fallback_chain_enabled/);
  });
});

describe("Fallback section persistence contracts", () => {
  it("keeps app settings query and mutation hooks available for settings screens", () => {
    const source = readSource(SETTINGS_QUERIES_PATH);

    expect(source).toMatch(/export function useAppSettings/);
    expect(source).toMatch(/export function useUpdateAppSettings/);
  });

  it("keeps using the canonical shared schemas for app settings and fallback targets", () => {
    const apiSource = readSource(SETTINGS_API_PATH);

    expect(apiSource).toMatch(/AppSettingsOutSchema/);
    expect(apiSource).toMatch(/SettingsFallbackResponseSchema/);
    expect(apiSource).toMatch(/from\s+"@runsight\/shared\/zod"/);
    expect(apiSource).toMatch(/return AppSettingsOutSchema\.parse\(res\);/);
    expect(apiSource).toMatch(/return SettingsFallbackResponseSchema\.parse\(res\);/);
  });
});
