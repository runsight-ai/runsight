import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const UI_DIR = resolve(__dirname, "..");
const STORIES_DIR = resolve(__dirname, "..", "..", "..", "stories");

function readComponent(filename: string): string {
  return readFileSync(resolve(UI_DIR, filename), "utf-8");
}

function readStory(filename: string): string {
  return readFileSync(resolve(STORIES_DIR, filename), "utf-8");
}

describe("Button and Dialog shared contracts", () => {
  it('keeps "icon-sm" as part of the shared button source contract', () => {
    const source = readComponent("button.tsx");

    expect(source).toContain('"icon-sm"');
  });

  it('Button does not define an "outline" variant in the shared contract', () => {
    const source = readComponent("button.tsx");

    expect(source).not.toMatch(/variant:\s*\{[\s\S]*outline\s*:/);
  });

  it('Dialog.stories.tsx does not use variant="outline"', () => {
    const source = readStory("Dialog.stories.tsx");

    expect(source).not.toMatch(/variant="outline"/);
  });
});
