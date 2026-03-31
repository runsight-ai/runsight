import { describe, expect, it } from "vitest";
import { existsSync } from "node:fs";
import { resolve } from "node:path";

const SRC_DIR = resolve(__dirname, "..", "..");

const REMOVED_SURFACES = [
  "features/workflows/WorkflowList.tsx",
  "features/runs/RunList.tsx",
  "features/flows/RunsTab.tsx",
  "features/sidebar/TaskList.tsx",
  "features/sidebar/StepList.tsx",
];

describe("RUN-431 dead surface cleanup", () => {
  for (const relativePath of REMOVED_SURFACES) {
    it(`${relativePath} is deleted from the GUI source tree`, () => {
      expect(
        existsSync(resolve(SRC_DIR, relativePath)),
        `Expected ${relativePath} to be removed`,
      ).toBe(false);
    });
  }
});
