import { describe, expect, it } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

const SRC_DIR = resolve(__dirname, "../../..");
const FEATURE_DIR = resolve(SRC_DIR, "features", "souls");
const HOOK_PATH = resolve(FEATURE_DIR, "useSoulForm.ts");
const PICKER_PATH = resolve(FEATURE_DIR, "SoulAvatarColorPicker.tsx");

function read(path: string): string {
  return readFileSync(path, "utf-8");
}

describe("RUN-447 file creation", () => {
  it("creates useSoulForm.ts under features/souls", () => {
    expect(existsSync(HOOK_PATH)).toBe(true);
  });

  it("creates SoulAvatarColorPicker.tsx under features/souls", () => {
    expect(existsSync(PICKER_PATH)).toBe(true);
  });
});

describe("SoulAvatarColorPicker contract (RUN-447)", () => {
  it("exports a SoulAvatarColorPicker component", () => {
    const source = read(PICKER_PATH);
    expect(source).toMatch(/export\s+(function|const)\s+SoulAvatarColorPicker/);
  });

  it("renders six clickable color swatches for avatar colors", () => {
    const source = read(PICKER_PATH);
    expect(source).toMatch(/button/);
    expect(source).toMatch(/aria-label=.*avatar color/);
    const swatchMatches = source.match(/value:\s*["'][^"']+["']/g) ?? [];
    expect(swatchMatches.length).toBeGreaterThanOrEqual(6);
  });
});

describe("useSoulForm public shape (RUN-447)", () => {
  it("exports a useSoulForm hook", () => {
    const source = read(HOOK_PATH);
    expect(source).toMatch(/export\s+(function|const)\s+useSoulForm/);
  });

  it("defines form values for name, avatarColor, providerId, provider, modelId, systemPrompt, tools, temperature, maxTokens, and maxToolIterations", () => {
    const source = read(HOOK_PATH);
    expect(source).toMatch(/interface\s+SoulFormValues|type\s+SoulFormValues/);
    expect(source).toMatch(/name:\s*string/);
    expect(source).toMatch(/avatarColor:\s*string/);
    expect(source).toMatch(/providerId:\s*string\s*\|\s*null/);
    expect(source).toMatch(/provider:\s*string\s*\|\s*null/);
    expect(source).toMatch(/modelId:\s*string\s*\|\s*null/);
    expect(source).toMatch(/systemPrompt:\s*string/);
    expect(source).toMatch(/tools:\s*string\[\]/);
    expect(source).toMatch(/temperature:\s*number/);
    expect(source).toMatch(/maxTokens:\s*number\s*\|\s*null/);
    expect(source).toMatch(/maxToolIterations:\s*number/);
  });

  it("does not include a skills field in MVP form state", () => {
    const source = read(HOOK_PATH);
    expect(source).not.toMatch(/\bskills\s*:/);
  });
});

describe("useSoulForm behavior contract (RUN-447)", () => {
  it("tracks dirty state and exposes a setField-style update path", () => {
    const source = read(HOOK_PATH);
    expect(source).toMatch(/\bisDirty\b/);
    expect(source).toMatch(/setField/);
    expect(source).toMatch(/setValues|useState/);
  });

  it("maps the submit payload to role/system_prompt/model_name/provider/tools/max_tokens/max_tool_iterations/avatar_color", () => {
    const source = read(HOOK_PATH);
    expect(source).toMatch(/role:\s*values\.name/);
    expect(source).toMatch(/system_prompt:\s*values\.systemPrompt/);
    expect(source).toMatch(/model_name:\s*values\.modelId/);
    expect(source).toMatch(/provider:\s*values\.provider/);
    expect(source).toMatch(/tools:\s*values\.tools/);
    expect(source).toMatch(/temperature:\s*values\.temperature/);
    expect(source).toMatch(/max_tokens:\s*values\.maxTokens/);
    expect(source).toMatch(/max_tool_iterations:\s*values\.maxToolIterations/);
    expect(source).toMatch(/avatar_color:\s*values\.avatarColor/);
    expect(source).not.toMatch(/\bname:\s*values\.name/);
  });

  it("never writes max_tool_iterations as null into the submit payload", () => {
    const source = read(HOOK_PATH);
    expect(source).not.toMatch(/max_tool_iterations:\s*[^,\n]*null/);
  });

  it("clears modelId and mirrors provider when provider selection changes", () => {
    const source = read(HOOK_PATH);
    expect(source).toMatch(/providerId/);
    expect(source).toMatch(/provider/);
    expect(source).toMatch(/modelId:\s*null|modelId\s*=\s*null/);
  });

  it("prefers soul.provider for edit initialization and still references model-based fallback for legacy souls", () => {
    const source = read(HOOK_PATH);
    expect(source).toMatch(/soul\.provider/);
    expect(source).toMatch(/soul\.model_name/);
  });
});
