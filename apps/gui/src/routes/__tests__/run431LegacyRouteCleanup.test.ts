import { describe, expect, it } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

const SRC_DIR = resolve(__dirname, "../..");
const ROUTES_PATH = resolve(SRC_DIR, "routes", "index.tsx");

function readRoutesSource(): string {
  return readFileSync(ROUTES_PATH, "utf-8");
}

describe("RUN-431 legacy list route cleanup", () => {
  it("redirects /workflows to /flows instead of mounting the deleted WorkflowList page", () => {
    const source = readRoutesSource();

    expect(source).toMatch(/path:\s*["']workflows["'][\s\S]*Navigate\s+to=["']\/flows["']\s+replace/);
    expect(source).not.toMatch(/features\/workflows\/WorkflowList/);
  });

  it("redirects /runs to /flows?tab=runs instead of mounting the deleted RunList page", () => {
    const source = readRoutesSource();

    expect(source).toMatch(
      /path:\s*["']runs["'][\s\S]*Navigate\s+to=["']\/flows\?tab=runs["']\s+replace/,
    );
    expect(source).not.toMatch(/features\/runs\/RunList/);
  });

  it("removes the /tasks and /steps routes entirely", () => {
    const source = readRoutesSource();

    expect(source).not.toMatch(/path:\s*["']tasks["']/);
    expect(source).not.toMatch(/path:\s*["']steps["']/);
    expect(source).not.toMatch(/features\/sidebar\/TaskList/);
    expect(source).not.toMatch(/features\/sidebar\/StepList/);
  });

  it("keeps the editor and run detail routes working", () => {
    const source = readRoutesSource();

    expect(source).toMatch(/path:\s*["']workflows\/:id\/edit["']/);
    expect(source).toMatch(/path:\s*["']runs\/:id["']/);
  });
});

describe("RUN-431 stale list-page files are deleted", () => {
  const removedFiles = [
    "features/workflows/WorkflowList.tsx",
    "features/workflows/NewWorkflowModal.tsx",
    "features/runs/RunList.tsx",
    "features/sidebar/TaskList.tsx",
    "features/sidebar/StepList.tsx",
  ];

  for (const relativePath of removedFiles) {
    it(`${relativePath} is removed from the GUI source tree`, () => {
      const filePath = resolve(SRC_DIR, relativePath);

      expect(existsSync(filePath), `Expected ${relativePath} to be deleted`).toBe(false);
    });
  }
});
