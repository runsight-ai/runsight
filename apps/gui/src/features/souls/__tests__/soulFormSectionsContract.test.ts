import { describe, expect, it } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

const SRC_DIR = resolve(__dirname, "../../..");
const FEATURE_DIR = resolve(SRC_DIR, "features", "souls");

const SECTION_PATHS = {
  body: resolve(FEATURE_DIR, "SoulFormBody.tsx"),
  section: resolve(FEATURE_DIR, "SoulFormSection.tsx"),
  identity: resolve(FEATURE_DIR, "SoulIdentitySection.tsx"),
  model: resolve(FEATURE_DIR, "SoulModelSection.tsx"),
  prompt: resolve(FEATURE_DIR, "SoulPromptSection.tsx"),
  tools: resolve(FEATURE_DIR, "SoulToolsSection.tsx"),
  advanced: resolve(FEATURE_DIR, "SoulAdvancedSection.tsx"),
} as const;

function read(path: string): string {
  return readFileSync(path, "utf-8");
}

describe("RUN-448 file creation", () => {
  it("creates SoulFormBody and all section components under features/souls", () => {
    expect(existsSync(SECTION_PATHS.body)).toBe(true);
    expect(existsSync(SECTION_PATHS.section)).toBe(true);
    expect(existsSync(SECTION_PATHS.identity)).toBe(true);
    expect(existsSync(SECTION_PATHS.model)).toBe(true);
    expect(existsSync(SECTION_PATHS.prompt)).toBe(true);
    expect(existsSync(SECTION_PATHS.tools)).toBe(true);
    expect(existsSync(SECTION_PATHS.advanced)).toBe(true);
  });
});

describe("SoulFormSection contract (RUN-448)", () => {
  it("exports a reusable section container with title, collapsible support, and tokenized heading styles", () => {
    const source = read(SECTION_PATHS.section);
    expect(source).toMatch(/export\s+(function|const)\s+SoulFormSection/);
    expect(source).toMatch(/title:\s*string/);
    expect(source).toMatch(/collapsible\??:\s*boolean/);
    expect(source).toMatch(/defaultOpen\??:\s*boolean/);
    expect(source).toMatch(/Chevron|chevron/i);
    expect(source).toMatch(/text-sm/);
    expect(source).toMatch(/font-semibold/);
    expect(source).toMatch(/uppercase/);
    expect(source).toMatch(/tracking-wider/);
  });
});

describe("SoulIdentitySection contract (RUN-448)", () => {
  it("renders Name input plus SoulAvatarColorPicker", () => {
    const source = read(SECTION_PATHS.identity);
    expect(source).toMatch(/export\s+(function|const)\s+SoulIdentitySection/);
    expect(source).toMatch(/Input/);
    expect(source).toMatch(/SoulAvatarColorPicker/);
    expect(source).toMatch(/name:\s*string/);
    expect(source).toMatch(/avatarColor:\s*string/);
    expect(source).toMatch(/onNameChange/);
    expect(source).toMatch(/onAvatarColorChange/);
  });
});

describe("SoulModelSection contract (RUN-448)", () => {
  it("uses configured providers plus the model catalog to drive provider and model selects", () => {
    const source = read(SECTION_PATHS.model);
    expect(source).toMatch(/export\s+(function|const)\s+SoulModelSection/);
    expect(source).toMatch(/useProviders/);
    expect(source).toMatch(/useModelsForProvider/);
    expect(source).toMatch(/Select/);
    expect(source).toMatch(/providerId:\s*string\s*\|\s*null/);
    expect(source).toMatch(/modelId:\s*string\s*\|\s*null/);
    expect(source).toMatch(/provider:\s*string\s*\|\s*null/);
    expect(source).toMatch(/onProviderChange/);
    expect(source).toMatch(/onModelChange/);
    expect(source).toMatch(/type/);
  });

  it("filters the models request by provider and shows provider-derived model ids", () => {
    const source = read(SECTION_PATHS.model);
    expect(source).toMatch(/useModelsForProvider\(\s*provider\s*\)/);
    expect(source).toMatch(/model_id/);
    expect(source).toMatch(/provider_name|name/);
  });

  it("disables the provider picker cleanly when no providers are configured", () => {
    const source = read(SECTION_PATHS.model);
    expect(source).toMatch(/hasConfiguredProviders/);
    expect(source).toMatch(/disabled=\{!hasConfiguredProviders\}/);
    expect(source).toMatch(/No providers configured/);
    expect(source).toMatch(/Add a provider in Settings before selecting a model/);
  });
});

describe("SoulPromptSection contract (RUN-448)", () => {
  it("renders a system-prompt textarea", () => {
    const source = read(SECTION_PATHS.prompt);
    expect(source).toMatch(/export\s+(function|const)\s+SoulPromptSection/);
    expect(source).toMatch(/Textarea/);
    expect(source).toMatch(/systemPrompt:\s*string/);
    expect(source).toMatch(/onSystemPromptChange/);
  });
});

describe("SoulToolsSection contract (RUN-448)", () => {
  it("renders a collapsed Tools section with assignable tool options and hides system-owned tools", () => {
    const source = read(SECTION_PATHS.tools);
    expect(source).toMatch(/export\s+(function|const)\s+SoulToolsSection/);
    expect(source).toMatch(/title=\{?["']Tools["']/);
    expect(source).toMatch(/defaultOpen=\{false\}|defaultOpen=\{?false\}?/);
    expect(source).toMatch(/tools:\s*string\[\]/);
    expect(source).toMatch(/onToolsChange/);
    expect(source).toMatch(/runsight\/http/);
    expect(source).toMatch(/runsight\/file-io/);
    expect(source).toMatch(/delegate/i);
    expect(source).toMatch(/automatically|block/i);
    expect(source).not.toMatch(/value:\s*["']runsight\/delegate["']/);
    expect(source).not.toMatch(/This soul has no tools enabled yet|This soul does not have any tools enabled yet/);
  });
});

describe("SoulAdvancedSection contract (RUN-448)", () => {
  it("renders temperature, max tokens, and max tool iterations controls", () => {
    const source = read(SECTION_PATHS.advanced);
    expect(source).toMatch(/export\s+(function|const)\s+SoulAdvancedSection/);
    expect(source).toMatch(/Slider|input[^]*type=["']range["']/);
    expect(source).toMatch(/temperature:\s*number/);
    expect(source).toMatch(/maxTokens:\s*number\s*\|\s*null/);
    expect(source).toMatch(/maxToolIterations:\s*number/);
    expect(source).toMatch(/onTemperatureChange/);
    expect(source).toMatch(/onMaxTokensChange/);
    expect(source).toMatch(/onMaxToolIterationsChange/);
    expect(source).toMatch(/0\s*-\s*2|step=\{?0\.1\}?|max=\{?2\}?/);
    expect(source).toMatch(/min=\{?1\}?/);
    expect(source).toMatch(/max=\{?50\}?/);
  });
});

describe("SoulFormBody composition contract (RUN-448)", () => {
  it("composes all five content sections and passes form bindings through", () => {
    const source = read(SECTION_PATHS.body);
    expect(source).toMatch(/export\s+(function|const)\s+SoulFormBody/);
    expect(source).toMatch(/SoulIdentitySection/);
    expect(source).toMatch(/SoulModelSection/);
    expect(source).toMatch(/SoulPromptSection/);
    expect(source).toMatch(/SoulToolsSection/);
    expect(source).toMatch(/SoulAdvancedSection/);
  });
});
