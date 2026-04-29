/**
 * Frontend build cleanup contract coverage.
 *
 * These tests keep the contract focused on build outcomes first:
 * 1. The GUI build should complete cleanly.
 * 2. Story/test files should be outside the app TypeScript build graph.
 * 3. The canonical flows workflow UI must stop reading phantom fields that do not exist on WorkflowResponse.
 * 4. The GUI keeps a real compact icon button call site.
 */

import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
import ts from "typescript";

const FEATURES_TESTS_DIR = __dirname;
const SRC_DIR = resolve(FEATURES_TESTS_DIR, "..", "..");
const GUI_ROOT = resolve(SRC_DIR, "..");
const REPO_ROOT = resolve(GUI_ROOT, "..", "..");

const WORKFLOW_ROW_PATH = resolve(SRC_DIR, "features", "flows", "WorkflowRow.tsx");
const WORKFLOWS_TAB_PATH = resolve(SRC_DIR, "features", "flows", "WorkflowsTab.tsx");
const PAGE_HEADER_PATH = resolve(SRC_DIR, "components", "shared", "PageHeader.tsx");
const TSCONFIG_PATH = resolve(GUI_ROOT, "tsconfig.json");

function readSource(filePath: string): string {
  return readFileSync(filePath, "utf-8");
}

function getBuildRootFileNames(): string[] {
  const parsedConfig = ts.getParsedCommandLineOfConfigFile(
    TSCONFIG_PATH,
    {},
    {
      ...ts.sys,
      onUnRecoverableConfigFileDiagnostic: (diagnostic) => {
        throw new Error(ts.flattenDiagnosticMessageText(diagnostic.messageText, "\n"));
      },
    },
  );

  if (!parsedConfig) {
    throw new Error("TypeScript could not parse apps/gui/tsconfig.json");
  }

  return parsedConfig.fileNames.map((fileName) => resolve(fileName));
}

describe("GUI build contracts", () => {
  it("pnpm -C apps/gui run build succeeds cleanly", () => {
    expect(() =>
      execFileSync("pnpm", ["-C", "apps/gui", "run", "build"], {
        cwd: REPO_ROOT,
        stdio: "pipe",
      }),
    ).not.toThrow();
  }, 60_000);

  it("the app TypeScript build graph excludes known story and test files", () => {
    const rootFileNames = getBuildRootFileNames();

    expect(rootFileNames).not.toContain(resolve(__filename));
    expect(rootFileNames.some((fileName) => /\.stories\.[jt]sx?$/.test(fileName))).toBe(false);
  });
});

describe("canonical flows workflow UI uses WorkflowResponse safely", () => {
  const phantomFields = [
    "status",
    "updated_at",
    "created_at",
    "last_run_duration",
    "last_run_cost_usd",
    "last_run_completed_at",
    "step_count",
  ] as const;

  it("WorkflowRow.tsx does not read phantom workflow fields", () => {
    const source = readSource(WORKFLOW_ROW_PATH);

    for (const field of phantomFields) {
      expect(source).not.toMatch(new RegExp(`workflow\\.${field}\\b|w\\.${field}\\b|a\\.${field}\\b|b\\.${field}\\b`));
    }
  });

  it("WorkflowsTab.tsx does not read phantom workflow fields", () => {
    const source = readSource(WORKFLOWS_TAB_PATH);

    for (const field of phantomFields) {
      expect(source).not.toMatch(new RegExp(`workflow\\.${field}\\b|w\\.${field}\\b|a\\.${field}\\b|b\\.${field}\\b`));
    }
  });
});

describe('GUI compact icon button usage', () => {
  it("keeps at least one real GUI call site using size=\"icon-sm\"", () => {
    const pageHeaderSource = readSource(PAGE_HEADER_PATH);

    expect(pageHeaderSource).toMatch(/size="icon-sm"/);
  });
});
