/**
 * RED-TEAM tests for RUN-407 QA-004: frontend build cleanup contracts.
 *
 * These source/config guard tests express the accepted cleanup decisions:
 * 1. WorkflowList must stop reading phantom fields that do not exist on WorkflowResponse.
 * 2. The shared Button contract must keep support for size="icon-sm".
 * 3. Dialog stories must use only valid button variants.
 * 4. GUI build config must exclude story/test files from the app TypeScript build graph.
 */

import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const FEATURES_TESTS_DIR = __dirname;
const SRC_DIR = resolve(FEATURES_TESTS_DIR, "..", "..");
const GUI_ROOT = resolve(SRC_DIR, "..");

const WORKFLOW_LIST_PATH = resolve(SRC_DIR, "features", "workflows", "WorkflowList.tsx");
const BUTTON_PATH = resolve(SRC_DIR, "components", "ui", "button.tsx");
const DIALOG_STORY_PATH = resolve(SRC_DIR, "stories", "Dialog.stories.tsx");
const ZOD_TYPES_PATH = resolve(SRC_DIR, "types", "generated", "zod.ts");
const TSCONFIG_PATH = resolve(GUI_ROOT, "tsconfig.json");

function readSource(filePath: string): string {
  return readFileSync(filePath, "utf-8");
}

function readJson<T>(filePath: string): T {
  return JSON.parse(readSource(filePath)) as T;
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

describe("RUN-407: WorkflowList build-safe WorkflowResponse usage", () => {
  const phantomFields = [
    "status",
    "updated_at",
    "created_at",
    "last_run_duration",
    "last_run_cost_usd",
    "last_run_completed_at",
    "step_count",
    "block_count",
  ] as const;

  it("generated WorkflowResponse contract does not contain the old phantom fields", () => {
    const workflowResponseFields = extractWorkflowResponseFields();

    for (const field of phantomFields) {
      expect(workflowResponseFields).not.toContain(field);
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
  it('declares "icon-sm" inside the shared button size variants', () => {
    const source = readSource(BUTTON_PATH);

    expect(source).toMatch(/size:\s*\{[\s\S]*"icon-sm"\s*:/);
  });

  it('keeps an icon-only compound variant for size "icon-sm"', () => {
    const source = readSource(BUTTON_PATH);

    expect(source).toMatch(/\{\s*variant:\s*"icon-only",\s*size:\s*"icon-sm",\s*className:\s*"[^"]+"\s*\}/);
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

describe("RUN-407: GUI TypeScript build graph excludes stories and tests", () => {
  type TsConfig = {
    include?: string[];
    exclude?: string[];
  };

  it("tsconfig.json excludes test files from the app build graph", () => {
    const tsconfig = readJson<TsConfig>(TSCONFIG_PATH);

    expect(tsconfig.exclude).toEqual(
      expect.arrayContaining([
        "src/**/*.test.*",
        "src/**/*.spec.*",
        "src/**/__tests__/**",
      ]),
    );
  });

  it("tsconfig.json excludes Storybook story files from the app build graph", () => {
    const tsconfig = readJson<TsConfig>(TSCONFIG_PATH);

    expect(tsconfig.exclude).toEqual(
      expect.arrayContaining([
        "src/**/*.stories.*",
      ]),
    );
  });
});
