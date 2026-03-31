import { describe, expect, it } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

const SRC_DIR = resolve(__dirname, "../../..");
const FEATURE_DIR = resolve(SRC_DIR, "features", "souls");
const PAGE_PATH = resolve(FEATURE_DIR, "SoulLibraryPage.tsx");
const PAGE_SOURCE = existsSync(PAGE_PATH) ? readFileSync(PAGE_PATH, "utf-8") : "";

function readPageSource(): string {
  return PAGE_SOURCE;
}

describe("RUN-452 file creation", () => {
  it("creates features/souls/SoulLibraryPage.tsx", () => {
    expect(existsSync(PAGE_PATH)).toBe(true);
  });
});

describe("RUN-452 SoulLibraryPage contract", () => {
  it("builds the page from PageHeader and DataTable directly, without CrudListPage or SoulModals", () => {
    const source = readPageSource();

    expect(source).toMatch(/export\s+(function|const)\s+(Component|SoulLibraryPage)/);
    expect(source).toMatch(/PageHeader/);
    expect(source).toMatch(/DataTable/);
    expect(source).not.toMatch(/CrudListPage/);
    expect(source).not.toMatch(/SoulModals/);
    expect(source).not.toMatch(/SoulList/);
  });

  it("renders only the current contract columns and omits Last Modified", () => {
    const source = readPageSource();

    expect(source).toMatch(/Name|role/);
    expect(source).toMatch(/Model/);
    expect(source).toMatch(/Provider/);
    expect(source).toMatch(/Used In/);
    expect(source).not.toMatch(/Last Modified/);
  });

  it("wires create and edit actions to /souls/new and /souls/:id/edit", () => {
    const source = readPageSource();

    expect(source).toMatch(/\/souls\/new/);
    expect(source).toMatch(/\/souls\/:id\/edit/);
    expect(source).toMatch(/navigate\([^)]*\/souls\/new/);
    expect(source).toMatch(/navigate\([^)]*\/souls\/:id\/edit/);
  });

  it("handles Used In ordering intentionally with a numeric comparator or equivalent sort step", () => {
    const source = readPageSource();

    expect(source).toMatch(/workflow_count|workflowCount/);
    expect(source).toMatch(/sort|sorted|toSorted|compare/);
    expect(source).toMatch(/Number\(|parseInt|numeric:\s*true|workflow_count\s*-\s*workflow_count/);
  });
});
