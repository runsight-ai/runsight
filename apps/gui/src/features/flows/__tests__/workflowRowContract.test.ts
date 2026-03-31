import { describe, expect, it } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

const FEATURE_DIR = resolve(__dirname, "..");

function readFeatureSource(fileName: string): string {
  const filePath = resolve(FEATURE_DIR, fileName);

  expect(
    existsSync(filePath),
    `Expected RUN-426 to add ${fileName} under apps/gui/src/features/flows`,
  ).toBe(true);

  return readFileSync(filePath, "utf-8");
}

describe("RUN-426 workflow row contract", () => {
  it("adds a WorkflowRow component for the two-line /flows list", () => {
    readFeatureSource("WorkflowRow.tsx");
  });

  it("renders line-one workflow metadata from the RUN-478/RUN-482 payload", () => {
    const source = readFeatureSource("WorkflowRow.tsx");

    expect(source).toMatch(/workflow\.name|name/);
    expect(source).toMatch(/workflow\.block_count|block_count/);
    expect(source).toMatch(/workflow\.commit_sha|commit_sha/);
    expect(source).toMatch(/workflow\.modified_at|modified_at/);
  });

  it("renders line-two health metrics from workflow.health", () => {
    const source = readFeatureSource("WorkflowRow.tsx");

    expect(source).toMatch(/workflow\.health\?\.run_count|health\?\.run_count/);
    expect(source).toMatch(/workflow\.health\?\.eval_pass_pct|health\?\.eval_pass_pct/);
    expect(source).toMatch(/workflow\.health\?\.total_cost_usd|health\?\.total_cost_usd/);
    expect(source).toMatch(/workflow\.health\?\.regression_count|health\?\.regression_count/);
  });

  it("handles partial-state workflows with no runs yet using zero and dash fallbacks", () => {
    const source = readFeatureSource("WorkflowRow.tsx");

    expect(source).toMatch(/run_count[\s\S]*===?\s*0|!\s*workflow\.health\?\.run_count/);
    expect(source).toMatch(/No runs yet|no runs yet|["']—["']/);
    expect(source).toMatch(/uncommitted|commit_sha[\s\S]*\?\?/);
  });

  it("keeps rows keyboard reachable and gives the trash action a descriptive aria-label", () => {
    const source = readFeatureSource("WorkflowRow.tsx");

    expect(source).toMatch(/role=["']listitem["']|<li\b/);
    expect(source).toMatch(/tabIndex=\{0\}|<button[\s\S]*onClick/);
    expect(source).toMatch(/onKeyDown/);
    expect(source).toMatch(/Enter|["'] ["']|Space/);
    expect(source).toMatch(/aria-label=\{`Delete \$\{workflow\.name \|\| "Untitled"\} workflow`\}|aria-label=["']Delete workflow["']/);
  });
});
