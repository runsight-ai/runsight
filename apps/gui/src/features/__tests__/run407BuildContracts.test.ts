/**
 * RED-TEAM tests for RUN-407 QA-004: frontend build cleanup contracts.
 *
 * These tests keep the contract focused on build outcomes first:
 * 1. The GUI build should complete cleanly.
 * 2. Story/test files should be outside the app TypeScript build graph.
 * 3. WorkflowList must stop reading phantom fields that do not exist on WorkflowResponse.
 * 4. The shared Button contract must keep support for size="icon-sm".
 * 5. Dialog stories must use only valid button variants.
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
const PACKAGES_ROOT = resolve(REPO_ROOT, "packages");

const WORKFLOW_LIST_PATH = resolve(SRC_DIR, "features", "workflows", "WorkflowList.tsx");
const BUTTON_PATH = resolve(PACKAGES_ROOT, "ui", "src", "components", "ui", "button.tsx");
const DIALOG_STORY_PATH = resolve(PACKAGES_ROOT, "ui", "src", "stories", "Dialog.stories.tsx");
const ZOD_TYPES_PATH = resolve(PACKAGES_ROOT, "shared", "src", "zod.ts");
const TSCONFIG_PATH = resolve(GUI_ROOT, "tsconfig.json");
const WORKFLOW_LIST_TEST_PATH = resolve(
  SRC_DIR,
  "features",
  "workflows",
  "__tests__",
  "WorkflowList.test.ts",
);

function readSource(filePath: string): string {
  return readFileSync(filePath, "utf-8");
}

function extractWorkflowResponseFields(): string[] {
  const source = readSource(ZOD_TYPES_PATH);
  const match = source.match(
    /export const WorkflowResponseSchema = z\.object\(\{([\s\S]*?)\n\}\);/,
  );

  if (!match) {
    throw new Error("Could not find WorkflowResponseSchema in generated zod types");
  }

  return match[1]
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const fieldMatch = line.match(/^([A-Za-z0-9_]+):\s/);
      if (!fieldMatch) {
        throw new Error(`Could not parse WorkflowResponseSchema field line: ${line}`);
      }
      return fieldMatch[1];
    });
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

describe("RUN-407: GUI build contracts", () => {
  it("pnpm -C apps/gui run build succeeds cleanly", () => {
    expect(() =>
      execFileSync("pnpm", ["-C", "apps/gui", "run", "build"], {
        cwd: REPO_ROOT,
        stdio: "pipe",
      }),
    ).not.toThrow();
  });

  it("the app TypeScript build graph excludes known story and test files", () => {
    const rootFileNames = getBuildRootFileNames();

    expect(rootFileNames).not.toContain(resolve(DIALOG_STORY_PATH));
    expect(rootFileNames).not.toContain(resolve(__filename));
    expect(rootFileNames).not.toContain(resolve(WORKFLOW_LIST_TEST_PATH));
  });
});

describe("RUN-407: WorkflowList build-safe WorkflowResponse usage", () => {
  const phantomFields = [
    "status",
    "updated_at",
    "created_at",
    "last_run_duration",
    "last_run_cost_usd",
    "last_run_completed_at",
    "step_count",
  ] as const;

  const run478Fields = ["block_count", "modified_at", "enabled", "commit_sha", "health"] as const;

  it("generated WorkflowResponse contract does not contain the old phantom fields", () => {
    const workflowResponseFields = extractWorkflowResponseFields();

    for (const field of phantomFields) {
      expect(workflowResponseFields).not.toContain(field);
    }
  });

  it("generated WorkflowResponse contract includes the RUN-478 workflow fields", () => {
    const workflowResponseFields = extractWorkflowResponseFields();

    for (const field of run478Fields) {
      expect(workflowResponseFields).toContain(field);
    }
  });

  it("WorkflowList.tsx does not read phantom workflow fields", () => {
    const source = readSource(WORKFLOW_LIST_PATH);

    for (const field of phantomFields) {
      expect(source).not.toMatch(new RegExp(`workflow\\.${field}\\b|w\\.${field}\\b|a\\.${field}\\b|b\\.${field}\\b`));
    }
  });
});

describe('RUN-407: Button shared contract keeps size "icon-sm"', () => {
  it('retains "icon-sm" as part of the shared button source contract', () => {
    const source = readSource(BUTTON_PATH);

    expect(source).toContain('"icon-sm"');
  });

  it("keeps at least one real GUI call site using size=\"icon-sm\"", () => {
    const workflowListSource = readSource(WORKFLOW_LIST_PATH);

    expect(workflowListSource).toMatch(/size="icon-sm"/);
  });
});

describe("RUN-407: Dialog stories use only valid Button variants", () => {
  it('Button does not define an "outline" variant in the shared contract', () => {
    const source = readSource(BUTTON_PATH);

    expect(source).not.toMatch(/variant:\s*\{[\s\S]*outline\s*:/);
  });

  it('Dialog.stories.tsx does not use variant="outline"', () => {
    const source = readSource(DIALOG_STORY_PATH);

    expect(source).not.toMatch(/variant="outline"/);
  });
});
