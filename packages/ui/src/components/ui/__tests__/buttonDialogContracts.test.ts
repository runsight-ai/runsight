import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const UI_DIR = resolve(__dirname, "..");

function readComponent(filename: string): string {
  return readFileSync(resolve(UI_DIR, filename), "utf-8");
}

describe("Button shared contracts", () => {
  it('keeps "icon-sm" as part of the shared button source contract', () => {
    const source = readComponent("button.tsx");

    expect(source).toContain('"icon-sm"');
  });

  it('Button does not define an "outline" variant in the shared contract', () => {
    const source = readComponent("button.tsx");

    expect(source).not.toMatch(/variant:\s*\{[\s\S]*outline\s*:/);
  });
});
