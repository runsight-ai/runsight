/**
 * RED-TEAM tests for RUN-737: Add explicit 404 handling for nonexistent
 * workflows in WorkflowSurface.
 *
 * AC1: Navigating to a nonexistent workflow ID shows a clear "not found" message
 * AC2: A back/home link is present
 * AC3: error-states.spec.ts does NOT use a permissive OR for the nonexistent-workflow test
 *
 * These tests verify the SOURCE TEXT of the components and the Playwright spec.
 * They are expected to FAIL against the current implementation because:
 *   - WorkflowSurface.tsx has no not-found/error branch for useWorkflow
 *   - error-states.spec.ts uses a broad permissive OR at line ~153
 *
 * Note: CanvasPage.tsx is not wired into the router (WorkflowSurface via
 * WorkflowEditRoute is the live code path), so it is not tested here.
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const CANVAS_DIR = resolve(__dirname, "..");
const E2E_DIR = resolve(__dirname, "../../../../../../testing/gui-e2e/tests");

function readCanvasFile(relativePath: string): string {
  return readFileSync(resolve(CANVAS_DIR, relativePath), "utf-8");
}

function readE2EFile(relativePath: string): string {
  return readFileSync(resolve(E2E_DIR, relativePath), "utf-8");
}

// ===========================================================================
// 1. WorkflowSurface.tsx — not-found branch for useWorkflow error/missing data
// ===========================================================================

describe("WorkflowSurface.tsx — 404 / not-found handling (RUN-737 AC1)", () => {
  const source = readCanvasFile("WorkflowSurface.tsx");

  it("destructures isError or error from useWorkflow", () => {
    // The hook call must capture error state: { data, isError } or { data, error }
    // Currently it only destructures `data`.
    expect(source).toMatch(/\b(?:isError|error|isNotFound|status)\b.*useWorkflow/s);
  });

  it("has a conditional branch that checks for not-found / error state", () => {
    // Must have something like: if (isError) ... or status === 'error'
    // or a check on the HTTP 404 status
    expect(source).toMatch(
      /(?:isError|error|isNotFound|status\s*===\s*['"]error['"]|404)/,
    );
  });

  it("renders a 'not found' or '404' message when workflow is missing", () => {
    // The JSX must contain text like "not found", "404", "Workflow not found"
    // etc. for the error state branch.
    expect(source).toMatch(
      /(?:not\s*found|404|Workflow\s+not\s+found|No\s+workflow)/i,
    );
  });

  it("renders a link back to the workflows list in the not-found branch", () => {
    // There must be an <a href> or <Link to> pointing to /flows
    // in the error-state branch of the component.
    expect(source).toMatch(/["'\/]flows["'\/]/);
    // That link must be inside an error/not-found rendering path, not just
    // a general link — assert that a link element appears near not-found text
    expect(source).toMatch(
      /(?:Link|<a).*\/flows|\/flows.*(?:Link|<a)/s,
    );
  });
});

// ===========================================================================
// 2. WorkflowSurface.tsx — useWorkflow error propagation contract
// ===========================================================================

describe("WorkflowSurface.tsx — useWorkflow result shape (RUN-737 AC1)", () => {
  const source = readCanvasFile("WorkflowSurface.tsx");

  it("does NOT silently ignore the error state of useWorkflow", () => {
    // The current code: const { data: workflow } = useWorkflow(workflowId)
    // After fix, the destructuring must include isError, error, or status.
    // We verify this by asserting the useWorkflow call site includes one of
    // those additional destructured values alongside `data`.
    // Pattern: `const { data: workflow, isError }` or `const { data, error }`
    expect(source).toMatch(
      /\{[^}]*(?:isError|error|isNotFound|status)[^}]*\}\s*=\s*useWorkflow|useWorkflow[^;]*\{[^}]*(?:isError|error|isNotFound|status)[^}]*\}/s,
    );
  });

  it("does NOT render a canvas when the workflow fetch has errored", () => {
    // There must be an early-return or conditional that prevents WorkflowCanvas
    // from being rendered in the not-found case.
    // We check that there is a guard before WorkflowCanvas usage.
    // The current code unconditionally renders WorkflowCanvas in the happy path
    // with no guard for the error case — this test expects that guard to exist.
    expect(source).toMatch(
      /(?:isError|error|isNotFound|status)[^}]*return|return[^}]*(?:not\s*found|404)/is,
    );
  });
});

// ===========================================================================
// 3. error-states.spec.ts — nonexistent workflow test must NOT use permissive OR
// ===========================================================================

describe("error-states.spec.ts — nonexistent workflow test is specific (RUN-737 AC3)", () => {
  const source = readE2EFile("error-states.spec.ts");

  it("does NOT use a permissive OR chain (hasLoading || hasNotFound || hasBackLink || hasReactFlow) for the nonexistent-workflow test", () => {
    // The current test at ~line 153 is:
    //   expect(hasLoading || hasNotFound || hasBackLink || hasReactFlow).toBe(true)
    // This is too permissive — it passes even when the canvas renders normally.
    // After RUN-737, the test must assert specifically on the not-found message.
    const hasPermissiveOrChain = /hasLoading\s*\|\|\s*hasNotFound\s*\|\|\s*hasBackLink\s*\|\|\s*hasReactFlow/.test(source);
    expect(hasPermissiveOrChain).toBe(false);
  });

  it("asserts specifically on a not-found message for the nonexistent workflow test", () => {
    // After the fix, the test should do something like:
    //   await expect(page.getByText(/not found|404/i)).toBeVisible()
    // using toBeVisible() as a Playwright assertion — NOT isVisible() as a boolean.
    // Verify: the nonexistent-workflow block contains a toBeVisible() assertion
    // on a not-found text pattern (not wrapped in a catch or boolean OR).
    const nonexistentBlock = source.match(
      /navigate to \/workflows\/nonexistent[\s\S]*?(?=\n\s*test\(|\n\s*test\.describe)/,
    )?.[0] ?? "";

    // Must have `toBeVisible` called as a Playwright expect assertion
    // on a not-found selector in the nonexistent-workflow test block.
    expect(nonexistentBlock).toMatch(
      /toBeVisible[\s\S]{0,200}(?:not\s*found|404)|(?:not\s*found|404)[\s\S]{0,200}toBeVisible/i,
    );
  });

  it("does NOT store isVisible() results in boolean variables that are OR-chained", () => {
    // The current pattern at line ~149-153 stores isVisible() as booleans:
    //   const hasLoading = await page.getByText(...).isVisible().catch(() => false);
    //   const hasNotFound = ...
    //   expect(hasLoading || hasNotFound || ...).toBe(true);
    //
    // After the fix, those boolean accumulator variables should be gone.
    // Specifically: no pattern of `const has<X> = await page...isVisible().catch`
    // should appear in the nonexistent-workflow test block.
    const nonexistentBlock = source.match(
      /navigate to \/workflows\/nonexistent[\s\S]*?(?=\n\s*test\(|\n\s*test\.describe)/,
    )?.[0] ?? "";

    // Count boolean isVisible intermediary variables (the permissive OR pattern)
    const booleanIsVisibleVars = (nonexistentBlock.match(/const\s+has\w+\s*=.*isVisible/g) ?? []).length;
    expect(booleanIsVisibleVars).toBe(0);
  });

  it("the nonexistent-workflow test uses toBeVisible() directly, not wrapped in a boolean catch", () => {
    // The current pattern: page.getByText(...).isVisible().catch(() => false)
    // This is a boolean escape hatch. After the fix, it should be:
    //   await expect(page.getByText(...)).toBeVisible({ timeout: ... })
    // Find the block for the nonexistent workflow test and check it uses toBeVisible
    // as a Playwright assertion, not as a boolean.
    const nonexistentBlock = source.match(
      /navigate to \/workflows\/nonexistent[\s\S]*?(?=\n\s*test\(|\n\s*test\.describe)/,
    )?.[0] ?? "";

    const hasIsVisibleCatch = /\.isVisible\(\)\.catch/.test(nonexistentBlock);
    expect(hasIsVisibleCatch).toBe(false);
  });
});
