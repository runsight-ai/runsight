/**
 * RED-TEAM tests for RUN-749: Run detail YAML tab shows current workflow, not historical snapshot.
 *
 * Problem: RunDetail passes run.workflow_id to YamlEditor which calls useWorkflow(workflowId)
 * — fetching the CURRENT workflow from disk. If the workflow was modified after the run,
 * the YAML shown differs from what actually ran.
 *
 * Intended behavior:
 *   1. run.commit_sha exists → fetch YAML from that commit via gitApi.getGitFile(sha, path)
 *   2. run.commit_sha absent → fall back to current workflow YAML
 *   3. YAML tab must remain read-only (already passing — not re-tested here)
 *
 * Approach: source-structure tests (readFileSync + pattern matching) — same convention
 * as runDetailYamlTab.test.ts and runDetailDecomposition.test.ts.
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "fs";
import { resolve } from "path";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const RUNS_DIR = resolve(__dirname, "..");
const readSource = (filename: string): string =>
  readFileSync(resolve(RUNS_DIR, filename), "utf-8");

// ---------------------------------------------------------------------------
// 1. RunDetail no longer passes workflow_id directly to YamlEditor
//    (current failing state: it does pass workflow_id)
// ---------------------------------------------------------------------------

describe("RunDetail YAML tab uses historical snapshot (RUN-749)", () => {
  it("does NOT pass run.workflow_id directly to YamlEditor without commit-sha guard", () => {
    const src = readSource("RunDetail.tsx");

    // The bug: <YamlEditor workflowId={run.workflow_id} ...> with no commit_sha branch.
    // After the fix there must be a commit_sha check BEFORE reaching YamlEditor with workflowId.
    // A plain, unguarded workflowId={run.workflow_id} prop (on the same line as YamlEditor)
    // is the broken pattern we must no longer see.
    const brokenPattern = /<YamlEditor\s[^>]*workflowId=\{run\.workflow_id\}/;
    expect(src).not.toMatch(brokenPattern);
  });

  it("checks run.commit_sha before deciding how to fetch YAML", () => {
    const src = readSource("RunDetail.tsx");

    // The fix must branch on commit_sha to choose historical vs. live fetch.
    const hasCommitShaGuard = /run\.commit_sha/.test(src);
    expect(hasCommitShaGuard).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// 2. RunDetail uses gitApi.getGitFile for the historical path
// ---------------------------------------------------------------------------

describe("RunDetail fetches historical YAML via gitApi (RUN-749)", () => {
  it("imports gitApi from the git API module", () => {
    const src = readSource("RunDetail.tsx");

    const importsGitApi =
      /import\s*\{[^}]*gitApi[^}]*\}\s*from/.test(src) ||
      /import\s+\*\s+as\s+\w+\s+from\s*["']@\/api\/git["']/.test(src);

    expect(importsGitApi).toBe(true);
  });

  it("calls gitApi.getGitFile with commitSha and workflowPath", () => {
    const src = readSource("RunDetail.tsx");

    // Must call getGitFile somewhere in the component
    expect(src).toMatch(/getGitFile/);
  });

  it("derives the workflow path from workflow_id using the standard path pattern", () => {
    const src = readSource("RunDetail.tsx");

    // useForkWorkflow uses: `custom/workflows/${run.workflow_id}.yaml`
    // RunDetail must use the same path convention when calling getGitFile.
    const hasWorkflowPath =
      /custom\/workflows\/\$\{/.test(src) ||
      /custom\/workflows\/.*workflow_id.*\.yaml/.test(src);

    expect(hasWorkflowPath).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// 3. RunDetail falls back to current-workflow YamlEditor when no commit_sha
// ---------------------------------------------------------------------------

describe("RunDetail falls back to current workflow when commit_sha is absent (RUN-749)", () => {
  it("still renders YamlEditor (or equivalent) in the no-commit-sha path", () => {
    const src = readSource("RunDetail.tsx");

    // The fall-back branch must still render something that shows the workflow YAML.
    // YamlEditor or a direct Monaco editor are both acceptable.
    const hasYamlFallback =
      /YamlEditor/.test(src) ||
      /MonacoEditor/.test(src) ||
      /monaco/.test(src);

    expect(hasYamlFallback).toBe(true);
  });

  it("the fallback path passes workflowId to YamlEditor inside a conditional guarded by !commit_sha", () => {
    const src = readSource("RunDetail.tsx");

    // The fix must wrap workflowId usage in a conditional that checks for missing commit_sha.
    // We look for a negation of commit_sha adjacent to or before the YamlEditor workflowId prop.
    // Pattern: either `!run.commit_sha` or `run.commit_sha ? ... : <YamlEditor workflowId=...>`
    const hasFallbackConditional =
      /!run\.commit_sha/.test(src) ||
      /run\.commit_sha\s*\?[\s\S]{0,300}YamlEditor/.test(src) ||
      /run\.commit_sha\s*\?[\s\S]{0,300}workflowId/.test(src);

    expect(hasFallbackConditional).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// 4. A dedicated hook or helper encapsulates the YAML-source logic
//    (preferred: keeps RunDetail thin and logic testable in isolation)
// ---------------------------------------------------------------------------

describe("Historical YAML logic is encapsulated outside RunDetail (RUN-749)", () => {
  it("RunDetail does NOT inline the getGitFile fetch as a raw useEffect with useState", () => {
    const src = readSource("RunDetail.tsx");

    // The fix should delegate to a hook (e.g. useRunYaml / useHistoricalYaml) or
    // a dedicated component (e.g. RunYamlPanel) rather than littering RunDetail
    // with raw useState + useEffect + gitApi calls for YAML fetching.
    //
    // Acceptable patterns:
    //   <RunYamlPanel ...>
    //   useRunYaml(...)
    //   useHistoricalYaml(...)
    //   <HistoricalYamlViewer ...>
    //
    // The test fails if none of these are present (implementation still inline).
    const hasDedicatedAbstraction =
      /RunYamlPanel/.test(src) ||
      /useRunYaml/.test(src) ||
      /useHistoricalYaml/.test(src) ||
      /HistoricalYamlViewer/.test(src) ||
      /RunYamlTab/.test(src);

    expect(hasDedicatedAbstraction).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// 5. YamlEditor itself does NOT own the commit-sha resolution logic
//    (single-responsibility: YamlEditor stays a pure display component)
// ---------------------------------------------------------------------------

describe("YamlEditor does not handle commit_sha resolution (RUN-749)", () => {
  it("YamlEditor props interface does not accept commitSha or workflowPath", () => {
    const src = readFileSync(
      resolve(__dirname, "../../canvas/YamlEditor.tsx"),
      "utf-8",
    );

    // YamlEditor should remain a simple display component driven by workflowId
    // (or a future `yaml` prop). It must NOT receive commitSha / workflowPath
    // because that couples it to the git resolution concern.
    expect(src).not.toMatch(/commitSha\s*[?:]?\s*string/);
    expect(src).not.toMatch(/workflowPath\s*[?:]?\s*string/);
  });

  it("YamlEditor still accepts workflowId or a direct yaml string prop", () => {
    const src = readFileSync(
      resolve(__dirname, "../../canvas/YamlEditor.tsx"),
      "utf-8",
    );

    const acceptsWorkflowId = /workflowId\s*[?:]/.test(src);
    const acceptsYamlProp = /\byaml\s*[?:]/.test(src);

    expect(acceptsWorkflowId || acceptsYamlProp).toBe(true);
  });
});
