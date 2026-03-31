import { describe, expect, it } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

const UI_DIR = resolve(__dirname, "..");
const PACKAGE_JSON = resolve(__dirname, "..", "..", "..", "..", "package.json");
const COMPONENT_PATH = resolve(UI_DIR, "tag-input.tsx");

function readComponent(): string {
  return readFileSync(COMPONENT_PATH, "utf-8");
}

describe("TagInput component file (RUN-446)", () => {
  it("creates tag-input.tsx under packages/ui/src/components/ui", () => {
    expect(existsSync(COMPONENT_PATH)).toBe(true);
  });

  it("is automatically exportable as @runsight/ui/tag-input via the package subpath wildcard", () => {
    const pkg = readFileSync(PACKAGE_JSON, "utf-8");
    expect(pkg).toContain('"./*": "./src/components/ui/*.tsx"');
    expect(existsSync(COMPONENT_PATH)).toBe(true);
  });
});

describe("TagInput public API (RUN-446)", () => {
  it("exports a TagInput component", () => {
    const source = readComponent();
    expect(source).toMatch(/export\s+(function|const)\s+TagInput/);
  });

  it("defines TagInputProps with label, placeholder, tags, and onChange", () => {
    const source = readComponent();
    expect(source).toMatch(/interface\s+TagInputProps/);
    expect(source).toMatch(/label:\s*string/);
    expect(source).toMatch(/placeholder:\s*string/);
    expect(source).toMatch(/tags:\s*string\[\]/);
    expect(source).toMatch(/onChange:\s*\(tags:\s*string\[\]\)\s*=>\s*void/);
  });
});

describe("TagInput behavior contracts (RUN-446)", () => {
  it("adds tags on Enter or comma and prevents the native input action", () => {
    const source = readComponent();
    expect(source).toMatch(/e\.key\s*===\s*"Enter"/);
    expect(source).toMatch(/e\.key\s*===\s*","/);
    expect(source).toMatch(/e\.preventDefault\(\)/);
    expect(source).toMatch(/addTag\(/);
  });

  it("removes the last tag on Backspace when the input is empty", () => {
    const source = readComponent();
    expect(source).toMatch(/e\.key\s*===\s*"Backspace"/);
    expect(source).toMatch(/inputValue\s*===\s*""/);
    expect(source).toMatch(/tags\.length\s*>\s*0/);
    expect(source).toMatch(/removeTag\(tags\.length\s*-\s*1\)/);
  });

  it("trims whitespace, ignores empty values, ignores duplicates, and clears the input after add", () => {
    const source = readComponent();
    expect(source).toMatch(/const\s+trimmed\s*=\s*value\.trim\(\)/);
    expect(source).toMatch(/if\s*\(\s*trimmed/);
    expect(source).toMatch(/!tags\.includes\(trimmed\)/);
    expect(source).toMatch(/setInputValue\(""\)/);
  });

  it("renders tags as Badge pills with an accessible remove button", () => {
    const source = readComponent();
    expect(source).toMatch(/<Badge[^>]+variant=\s*"neutral"/);
    expect(source).toMatch(/aria-label=\{`Remove \$\{tag\}`\}/);
    expect(source).toMatch(/onClick=\{\(\)\s*=>\s*removeTag\(i\)\}/);
  });
});

describe("TagInput visual contract (RUN-446)", () => {
  it("uses the required focus ring and border token classes on the container", () => {
    const source = readComponent();
    expect(source).toMatch(/flex\s+flex-wrap\s+gap-1\.5/);
    expect(source).toMatch(/border\s+border-border-default/);
    expect(source).toMatch(/rounded-md/);
    expect(source).toMatch(/px-2\s+py-1\.5/);
    expect(source).toMatch(/focus-within:ring-2/);
    expect(source).toMatch(/focus-within:ring-border-focus/);
  });

  it("uses a borderless growing input with placeholder behavior tied to tag count", () => {
    const source = readComponent();
    expect(source).toMatch(/className=.*flex-1.*min-w-\[120px\].*border-0/s);
    expect(source).toMatch(/placeholder=\{tags\.length\s*===\s*0\s*\?\s*placeholder\s*:\s*""\}/);
  });

  it("truncates long tag text and styles the remove button as muted until hover", () => {
    const source = readComponent();
    expect(source).toMatch(/max-w-\[200px\]/);
    expect(source).toMatch(/truncate/);
    expect(source).toMatch(/text-muted/);
    expect(source).toMatch(/hover:text-primary/);
  });
});
