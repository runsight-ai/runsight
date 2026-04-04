import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const SRC_DIR = resolve(__dirname, "../../..");

function readGuiSource(relativePath: string): string {
  return readFileSync(resolve(SRC_DIR, relativePath), "utf-8");
}

const SETTINGS_PAGE_PATH = "features/settings/SettingsPage.tsx";
const PROVIDERS_TAB_PATH = "features/settings/ProvidersTab.tsx";
const MODELS_TAB_PATH = "features/settings/ModelsTab.tsx";
const CONNECTION_FEEDBACK_PATH = "features/setup/components/ConnectionFeedback.tsx";

describe("Settings accessibility wiring", () => {
  it("provider actions use descriptive aria-labels", () => {
    const source = readGuiSource(PROVIDERS_TAB_PATH);
    expect(source).toMatch(/aria-label=\{`Test \$\{provider\.name\} connection`\}/);
    expect(source).toMatch(/aria-label=\{`Edit \$\{provider\.name\} provider`\}/);
    expect(source).toMatch(/aria-label=\{`Delete \$\{provider\.name\} provider`\}/);
  });

  it("provider status and enable toggle expose screen-reader labels", () => {
    const source = readGuiSource(PROVIDERS_TAB_PATH);
    expect(source).toMatch(/aria-label=\{`Enable \$\{provider\.name\} provider`\}/);
    expect(source).toMatch(
      /aria-label=\{`[^`]*\$\{provider\.name\}[^`]*status[^`]*\$\{getStatusLabel\(provider\.status\)\}[^`]*`\}|sr-only[\s\S]*provider\.name[\s\S]*getStatusLabel\(provider\.status\)/,
    );
  });

  it("fallback tab controls use descriptive aria-labels", () => {
    const source = readGuiSource(MODELS_TAB_PATH);
    expect(source).toMatch(/Enable fallback/);
    expect(source).toMatch(/aria-label=\{`Fallback provider for \$\{.*\}`\}/);
    expect(source).toMatch(/aria-label=\{`Fallback model for \$\{.*\}`\}/);
    expect(source).toMatch(/aria-label=\{`Clear fallback for \$\{.*\}`\}/);
    expect(source).not.toMatch(/default model/i);
    expect(source).not.toMatch(/model change/i);
    expect(source).not.toMatch(/aria-label=\{`Move \$\{name\} up`\}/);
    expect(source).not.toMatch(/aria-label=\{`Move \$\{name\} down`\}/);
  });

  it("fallback row keyboard order runs provider select then model select then clear button", () => {
    const source = readGuiSource(MODELS_TAB_PATH);
    expect(source).toMatch(
      /Fallback provider for[\s\S]*Fallback model for[\s\S]*Clear fallback for/,
    );
  });

  it("connection feedback announces status changes", () => {
    const source = readGuiSource(CONNECTION_FEEDBACK_PATH);
    expect(source).toMatch(/role="status"/);
    expect(source).toMatch(/aria-live="polite"/);
  });

  it("settings tabs are explicitly labelled and require Enter or Space to activate", () => {
    const source = readGuiSource(SETTINGS_PAGE_PATH);
    expect(source).toMatch(/<TabsList[^>]*aria-label="Settings sections"/);
    expect(source).toMatch(/<TabsList[^>]*activateOnFocus=\{false\}/);
  });
});
