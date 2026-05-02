import { describe, expect, it } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

const UI_DIR = resolve(__dirname, "..");
const PACKAGE_JSON = resolve(__dirname, "..", "..", "..", "..", "package.json");
const COMPONENT_PATH = resolve(UI_DIR, "tag-input.tsx");

function readComponent(): string {
  return readFileSync(COMPONENT_PATH, "utf-8");
}

describe("TagInput component file", () => {
  it("creates tag-input.tsx under packages/ui/src/components/ui", () => {
    expect(existsSync(COMPONENT_PATH)).toBe(true);
  });

  it("is publicly reachable as @runsight/ui/tag-input through an explicit retained package export", () => {
    const pkg = readFileSync(PACKAGE_JSON, "utf-8");
    expect(pkg).toContain('"./tag-input": "./src/components/ui/tag-input.tsx"');
    expect(pkg).not.toContain('"./*": "./src/components/ui/*.tsx"');
    expect(existsSync(COMPONENT_PATH)).toBe(true);
  });
});

describe("TagInput public API", () => {
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

describe("TagInput visual contract", () => {
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
    expect(source).toMatch(/<Badge[^>]+variant=\s*"neutral"/);
    expect(source).toMatch(/aria-label=\{`Remove \$\{tag\}`\}/);
    expect(source).toMatch(/max-w-\[200px\]/);
    expect(source).toMatch(/truncate/);
    expect(source).toMatch(/text-muted/);
    expect(source).toMatch(/hover:text-primary/);
  });
});
