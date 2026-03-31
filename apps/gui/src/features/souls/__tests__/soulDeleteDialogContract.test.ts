import { describe, expect, it } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

const APP_SRC_DIR = resolve(__dirname, "../../..");
const FEATURE_DIR = resolve(APP_SRC_DIR, "features", "souls");

const DIALOG_PATH = resolve(FEATURE_DIR, "SoulDeleteDialog.tsx");
const WARNING_PATH = resolve(FEATURE_DIR, "SoulUsageWarning.tsx");
const SOULS_API_PATH = resolve(APP_SRC_DIR, "api", "souls.ts");
const SOULS_QUERIES_PATH = resolve(APP_SRC_DIR, "queries", "souls.ts");

function readSource(path: string): string {
  expect(existsSync(path), `Expected ${path} to exist`).toBe(true);
  return readFileSync(path, "utf-8");
}

describe("RUN-451 file creation", () => {
  it("creates SoulDeleteDialog.tsx and SoulUsageWarning.tsx under features/souls", () => {
    expect(existsSync(DIALOG_PATH)).toBe(true);
    expect(existsSync(WARNING_PATH)).toBe(true);
  });
});

describe("SoulDeleteDialog contract (RUN-451)", () => {
  it("exports a dependency-aware delete dialog that loads usages when open and a soul id exist", () => {
    const source = readSource(DIALOG_PATH);

    expect(source).toMatch(/export\s+(function|const)\s+SoulDeleteDialog/);
    expect(source).toMatch(/useSoulUsages/);
    expect(source).toMatch(/open\s*&&\s*!!?soul\?\.\s*id|enabled:\s*open\s*&&\s*!!?soul\?\.\s*id/);
    expect(source).toMatch(/DialogContent|DialogFooter|DialogTitle/);
    expect(source).toMatch(/Loading|Spinner|loading/i);
    expect(source).toMatch(/Delete anyway/);
    expect(source).toMatch(/Could not check workflow usage/);
    expect(source).toMatch(/AlertTriangle/);
  });

  it("shows capped workflow badges and the +N more overflow indicator", () => {
    const source = readSource(DIALOG_PATH);

    expect(source).toMatch(/SoulUsageWarning/);
    expect(source).toMatch(/Badge/);
    expect(source).toMatch(/workflow_name/);
    expect(source).toMatch(/\+N more|\+\{N\} more/);
    expect(source).toMatch(/5/);
    expect(source).toMatch(/Delete "?\{?soul\.role\}?"/);
  });

  it("keeps the delete action enabled when usage lookup fails and closes without deleting on dismissal", () => {
    const source = readSource(DIALOG_PATH);

    expect(source).toMatch(/usage error|Could not check workflow usage/i);
    expect(source).toMatch(/Delete\s+Button|Button variant="danger"|variant="danger"/);
    expect(source).toMatch(/onOpenChange|Escape|X|close/i);
    expect(source).toMatch(/onClose/);
    expect(source).not.toMatch(/disable.*delete.*error/i);
  });
});

describe("SoulUsageWarning contract (RUN-451)", () => {
  it("exports a presentational warning component with required workflow names", () => {
    const source = readSource(WARNING_PATH);

    expect(source).toMatch(/export\s+(function|const)\s+SoulUsageWarning/);
    expect(source).toMatch(/workflow_name:\s*string/);
    expect(source).not.toMatch(/workflow_name:\s*string\s*\|\s*null/);
    expect(source).toMatch(/AlertTriangle/);
    expect(source).toMatch(/Badge/);
    expect(source).toMatch(/warning/i);
  });
});

describe("Soul delete plumbing contract (RUN-451)", () => {
  it("widen soulsApi.deleteSoul to accept force and append ?force=true", () => {
    const source = readSource(SOULS_API_PATH);

    expect(source).toMatch(/deleteSoul:\s*async\s*\(\s*id:\s*string\s*,\s*force/);
    expect(source).toMatch(/\?force=true|force=\$\{?force\}?/);
  });

  it("widen useDeleteSoul to pass force through to soulsApi.deleteSoul", () => {
    const source = readSource(SOULS_QUERIES_PATH);

    expect(source).toMatch(/useDeleteSoul/);
    expect(source).toMatch(/\{\s*id,\s*force\s*\}/);
    expect(source).toMatch(/soulsApi\.deleteSoul\(id,\s*force\)/);
  });
});
