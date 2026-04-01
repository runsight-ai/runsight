import { describe, expect, it } from "vitest";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { resolve, relative } from "node:path";

const SRC_DIR = resolve(__dirname, "../..");

function readSource(relativePath: string): string {
  return readFileSync(resolve(SRC_DIR, relativePath), "utf-8");
}

function sourceFileExists(relativePath: string): boolean {
  return existsSync(resolve(SRC_DIR, relativePath));
}

function listRuntimeFiles(dir: string): string[] {
  const entries = readdirSync(dir, { withFileTypes: true });
  const files: string[] = [];

  for (const entry of entries) {
    const fullPath = resolve(dir, entry.name);

    if (entry.isDirectory()) {
      if (entry.name === "__tests__") {
        continue;
      }
      files.push(...listRuntimeFiles(fullPath));
      continue;
    }

    if (!/\.(ts|tsx)$/.test(entry.name)) {
      continue;
    }

    files.push(relative(SRC_DIR, fullPath));
  }

  return files;
}

function findRuntimeReferences(pattern: RegExp, excludedFiles: string[] = []): string[] {
  return listRuntimeFiles(SRC_DIR)
    .filter((filePath) => !excludedFiles.includes(filePath))
    .filter((filePath) => pattern.test(readSource(filePath)));
}

function listFiles(dir: string): string[] {
  const entries = readdirSync(dir, { withFileTypes: true });
  const files: string[] = [];

  for (const entry of entries) {
    const fullPath = resolve(dir, entry.name);

    if (entry.isDirectory()) {
      files.push(...listFiles(fullPath));
      continue;
    }

    if (!/\.(ts|tsx)$/.test(entry.name)) {
      continue;
    }

    files.push(relative(SRC_DIR, fullPath));
  }

  return files;
}

function findTestReferences(pattern: RegExp, excludedFiles: string[] = []): string[] {
  return listFiles(SRC_DIR)
    .filter((filePath) => filePath.includes("__tests__/"))
    .filter((filePath) => !excludedFiles.includes(filePath))
    .filter((filePath) => pattern.test(readSource(filePath)));
}

const SHARED_DEAD_LEAF_FILES = [
  "components/shared/CrudListPage.tsx",
  "components/shared/NodeBadge.tsx",
  "components/shared/CostDisplay.tsx",
] as const;

describe("RUN-511 dead feature leaf cleanup", () => {
  it("removes dead route-retired feature leaves from disk", () => {
    expect(sourceFileExists("features/health/HealthPage.tsx")).toBe(false);
    expect(sourceFileExists("features/workflows/NewWorkflowModal.tsx")).toBe(false);
  });

  it("proves the retired health and workflow modal leaves are not reachable from live runtime imports", () => {
    const healthRefs = findRuntimeReferences(/HealthPage/, [
      "features/health/HealthPage.tsx",
    ]);
    const workflowModalRefs = findRuntimeReferences(/NewWorkflowModal/, [
      "features/workflows/NewWorkflowModal.tsx",
    ]);

    expect(healthRefs).toEqual([]);
    expect(workflowModalRefs).toEqual([]);
  });

  it("keeps the shipped router free of the retired health placeholder route", () => {
    const routesSource = readSource("routes/index.tsx");

    expect(routesSource).not.toMatch(/path:\s*["']health["']/);
    expect(routesSource).not.toMatch(/features\/health\/HealthPage/);
  });
});

describe("RUN-511 dead shared leaf cleanup", () => {
  it("removes dead shared leaf component files from the shipped runtime tree", () => {
    for (const filePath of SHARED_DEAD_LEAF_FILES) {
      expect(sourceFileExists(filePath)).toBe(false);
    }
  });

  it("proves the shared dead leaves are not reachable from live runtime imports", () => {
    const crudListRefs = findRuntimeReferences(/CrudListPage/, [
      "components/shared/CrudListPage.tsx",
      "components/shared/index.ts",
    ]);
    const nodeBadgeRefs = findRuntimeReferences(/NodeBadge/, [
      "components/shared/NodeBadge.tsx",
      "components/shared/index.ts",
    ]);
    const costDisplayRefs = findRuntimeReferences(/CostDisplay/, [
      "components/shared/CostDisplay.tsx",
      "components/shared/index.ts",
    ]);

    expect(crudListRefs).toEqual([]);
    expect(nodeBadgeRefs).toEqual([]);
    expect(costDisplayRefs).toEqual([]);
  });

  it("removes stale shared barrel exports tied only to deleted shared leaves", () => {
    const source = readSource("components/shared/index.ts");

    expect(source).not.toMatch(/CrudListPage/);
    expect(source).not.toMatch(/CrudListPageConfig/);
    expect(source).not.toMatch(/NodeBadge/);
    expect(source).not.toMatch(/NodeType/);
    expect(source).not.toMatch(/CostDisplay/);
  });

  it("does not keep shared dead leaves alive only through product-tree tests", () => {
    const crudListTestRefs = findTestReferences(/CrudListPage/, [
      "features/__tests__/run511DeadLeafCleanup.test.ts",
      "features/__tests__/screenTokenSweep.test.ts",
    ]);
    const nodeBadgeTestRefs = findTestReferences(/NodeBadge/, [
      "features/__tests__/run511DeadLeafCleanup.test.ts",
      "features/__tests__/screenTokenSweep.test.ts",
    ]);
    const costDisplayTestRefs = findTestReferences(/CostDisplay/, [
      "features/__tests__/run511DeadLeafCleanup.test.ts",
      "features/__tests__/screenTokenSweep.test.ts",
    ]);

    expect(crudListTestRefs).toEqual([]);
    expect(nodeBadgeTestRefs).toEqual([]);
    expect(costDisplayTestRefs).toEqual([]);
  });
});

describe("RUN-511 provider/setup boundary cleanup", () => {
  it("keeps SetupStartPage and ProviderSetup on live runtime paths", () => {
    expect(sourceFileExists("features/setup/SetupStartPage.tsx")).toBe(true);
    expect(sourceFileExists("components/provider/ProviderSetup.tsx")).toBe(true);

    const routesSource = readSource("routes/index.tsx");
    const providerModalSource = readSource("components/provider/ProviderModal.tsx");

    expect(routesSource).toMatch(/features\/setup\/SetupStartPage/);
    expect(providerModalSource).toMatch(/ALL_PROVIDERS/);
    expect(providerModalSource).toMatch(/from\s+["']\.\/ProviderSetup["']/);
  });

  it("removes stale hero and dropdown provider barrel exports that are not part of the supported surface", () => {
    const providerIndexSource = readSource("components/provider/index.ts");

    expect(providerIndexSource).not.toMatch(/HERO_PROVIDERS/);
    expect(providerIndexSource).not.toMatch(/DROPDOWN_PROVIDERS/);
  });

  it("keeps the supported provider barrel surface for live consumers", () => {
    const providerIndexSource = readSource("components/provider/index.ts");

    expect(providerIndexSource).toMatch(/ProviderModal/);
    expect(providerIndexSource).toMatch(/ProviderDef/);
    expect(providerIndexSource).toMatch(/TestStatus/);
  });
});
