/**
 * RED-TEAM tests for RUN-411: remove dead duplicate workflow action from WorkflowList.
 *
 * These source-guard tests assert that the Duplicate menu label is removed from
 * both render paths in WorkflowList.tsx and that the dead duplicate-workflow
 * TODO/commentary logging has been deleted as well.
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const WORKFLOW_LIST_PATH = resolve(__dirname, "..", "WorkflowList.tsx");

function readWorkflowListSource(): string {
  return readFileSync(WORKFLOW_LIST_PATH, "utf-8");
}

function countMatches(source: string, pattern: RegExp): number {
  return source.match(pattern)?.length ?? 0;
}

describe("WorkflowList duplicate action removal", () => {
  it("does not render a Duplicate action label in either workflow action menu", () => {
    const source = readWorkflowListSource();
    const duplicateLabels = countMatches(source, /^\s*Duplicate\s*$/gm);

    expect(duplicateLabels).toBe(0);
  });

  it("does not keep the duplicate-workflow TODO comment", () => {
    const source = readWorkflowListSource();

    expect(source).not.toMatch(/TODO:\s*Implement duplicate workflow/);
  });

  it("does not keep the duplicate-workflow console.log", () => {
    const source = readWorkflowListSource();

    expect(source).not.toMatch(/console\.log\(\s*["']Duplicate workflow:/);
  });
});
