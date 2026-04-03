import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const SRC_DIR = resolve(__dirname, "../../..");

function readSource(relativePath: string): string {
  return readFileSync(resolve(SRC_DIR, relativePath), "utf-8");
}

const PROVIDERS_TAB_PATH = "features/settings/ProvidersTab.tsx";
const MODELS_TAB_PATH = "features/settings/ModelsTab.tsx";

describe("ProvidersTab error state wiring", () => {
  it("reads the providers query error and refetch handles", () => {
    const source = readSource(PROVIDERS_TAB_PATH);
    expect(source).toMatch(/const\s*\{\s*data,\s*isLoading,\s*error,\s*refetch\s*\}\s*=\s*useProviders\(\)/);
  });

  it("renders the shared retryable error presentation", () => {
    const source = readSource(PROVIDERS_TAB_PATH);
    expect(source).toMatch(/AlertCircle/);
    expect(source).toMatch(/Failed to load providers/i);
    expect(source).toMatch(/error instanceof Error\s*\?\s*error\.message/);
    expect(source).toMatch(/Retry/);
  });

  it("tracks retry loading state while refetch is in flight", () => {
    const source = readSource(PROVIDERS_TAB_PATH);
    expect(source).toMatch(/useState\(false\)/);
    expect(source).toMatch(/isRetrying|retrying/);
    expect(source).toMatch(/set(?:Is)?Retrying\(true\)/);
    expect(source).toMatch(/await\s+refetch\(\)/);
    expect(source).toMatch(/finally\s*\{[\s\S]*set(?:Is)?Retrying\(false\)/);
  });

  it("disables the Retry button and swaps its label while retrying", () => {
    const source = readSource(PROVIDERS_TAB_PATH);
    expect(source).toMatch(/<Button[\s\S]*disabled=\{(?:is)?Retrying\}/);
    expect(source).toMatch(/(?:is)?Retrying\s*\?\s*"Retrying\.\.\."\s*:\s*"Retry"/);
  });
});

describe("ModelsTab error state wiring", () => {
  it("reads the fallback-targets query error and refetch handles", () => {
    const source = readSource(MODELS_TAB_PATH);
    expect(source).toMatch(
      /const\s*\{\s*data,\s*isLoading,\s*error,\s*refetch\s*\}\s*=\s*useFallbackTargets\(\)/,
    );
  });

  it("renders the shared retryable error presentation", () => {
    const source = readSource(MODELS_TAB_PATH);
    expect(source).toMatch(/AlertCircle/);
    expect(source).toMatch(/Failed to load fallback settings/i);
    expect(source).toMatch(/error instanceof Error\s*\?\s*error\.message/);
    expect(source).toMatch(/Retry/);
  });

  it("tracks retry loading state while refetch is in flight", () => {
    const source = readSource(MODELS_TAB_PATH);
    expect(source).toMatch(/useState\(false\)/);
    expect(source).toMatch(/isRetrying|retrying/);
    expect(source).toMatch(/set(?:Is)?Retrying\(true\)/);
    expect(source).toMatch(/await\s+refetch\(\)/);
    expect(source).toMatch(/finally\s*\{[\s\S]*set(?:Is)?Retrying\(false\)/);
  });

  it("disables the Retry button and swaps its label while retrying", () => {
    const source = readSource(MODELS_TAB_PATH);
    expect(source).toMatch(/<Button[\s\S]*disabled=\{(?:is)?Retrying\}/);
    expect(source).toMatch(/(?:is)?Retrying\s*\?\s*"Retrying\.\.\."\s*:\s*"Retry"/);
  });
});
