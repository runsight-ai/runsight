import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { generateForkName } from "../forkUtils";

const FORK_HOOK_PATH = resolve(__dirname, "..", "useForkWorkflow.ts");

function readForkHookSource(): string {
  return readFileSync(FORK_HOOK_PATH, "utf-8");
}

describe("RUN-834 fork workflow verification", () => {
  it("rewrites fork YAML with a new embedded workflow id and preserves nested refs", () => {
    const source = readForkHookSource();

    expect(source).toContain("modified.id = forkWorkflowId");
    expect(source).toContain('modified.kind = "workflow"');
    expect(source).toContain("modified.enabled = false");
    expect(source).toContain("modified.workflow = isPlainObject(modified.workflow)");
    expect(source).toContain('workflowsApi.createWorkflow({');
    expect(source).toContain("commit: false");
  });

  it("caps generated fork ids to the backend workflow id length limit", () => {
    const longName = `Source ${"workflow ".repeat(30)}`;

    const forkId = generateForkName(longName);

    expect(forkId).toMatch(/^drft-[a-z0-9-]+-[a-z0-9]{4}$/);
    expect(forkId.length).toBeLessThanOrEqual(100);
  });
});
