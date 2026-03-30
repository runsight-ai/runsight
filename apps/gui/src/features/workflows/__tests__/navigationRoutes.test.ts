/**
 * RED-TEAM tests for RUN-420: WorkflowList + NewWorkflowModal navigate to wrong route.
 *
 * Both WorkflowList.tsx and NewWorkflowModal.tsx currently navigate to
 * `/workflows/:id` (bare ReactFlow canvas — WorkflowCanvas) instead of
 * `/workflows/:id/edit` (full CanvasPage with topbar, YAML editor, palette).
 *
 * These source-reading tests assert that every navigate() call targeting a
 * single workflow uses the `/edit` suffix so users always land on the full
 * CanvasPage, never the bare canvas dead-end.
 *
 * Expected failures (current state):
 *   - WorkflowList.tsx line 157: navigate(`/workflows/${workflow.id}`) — missing /edit
 *   - NewWorkflowModal.tsx line 62: navigate(`/workflows/${result.id}`) — missing /edit
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const FEATURES_DIR = resolve(__dirname, "..");

function readSource(fileName: string): string {
  return readFileSync(resolve(FEATURES_DIR, fileName), "utf-8");
}

/**
 * Extract all navigate() calls that target /workflows/${...} routes.
 * Returns an array of the matched template-literal strings.
 *
 * Matches patterns like:
 *   navigate(`/workflows/${workflow.id}`)
 *   navigate(`/workflows/${result.id}`)
 *   navigate(`/workflows/${id}/edit`)
 */
function extractWorkflowNavigateCalls(source: string): string[] {
  const pattern = /navigate\(`\/workflows\/\$\{[^}]+\}[^`]*`\)/g;
  return source.match(pattern) ?? [];
}

// ---------------------------------------------------------------------------
// 1. WorkflowList.tsx — row click navigates to /workflows/:id/edit
// ---------------------------------------------------------------------------

describe("WorkflowList navigates to /workflows/:id/edit", () => {
  let source: string;

  it("has at least one navigate() call targeting a workflow route", () => {
    source = readSource("WorkflowList.tsx");
    const calls = extractWorkflowNavigateCalls(source);
    expect(calls.length).toBeGreaterThanOrEqual(1);
  });

  it("every workflow navigate() call includes the /edit suffix", () => {
    source = readSource("WorkflowList.tsx");
    const calls = extractWorkflowNavigateCalls(source);

    for (const call of calls) {
      expect(call, `Expected /edit suffix in: ${call}`).toMatch(/\/edit/);
    }
  });

  it("does NOT have any navigate() to bare /workflows/:id (without /edit)", () => {
    source = readSource("WorkflowList.tsx");
    // Match navigate(`/workflows/${...}`) that ends right after the interpolation
    // i.e., no /edit after the closing }
    const barePattern = /navigate\(`\/workflows\/\$\{[^}]+\}`\)/g;
    const bareMatches = source.match(barePattern) ?? [];

    expect(
      bareMatches.length,
      `Found bare navigate() calls without /edit: ${bareMatches.join(", ")}`,
    ).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// 2. NewWorkflowModal.tsx — creation navigates to /workflows/:id/edit
// ---------------------------------------------------------------------------

describe("NewWorkflowModal navigates to /workflows/:id/edit", () => {
  let source: string;

  it("has at least one navigate() call targeting a workflow route", () => {
    source = readSource("NewWorkflowModal.tsx");
    const calls = extractWorkflowNavigateCalls(source);
    expect(calls.length).toBeGreaterThanOrEqual(1);
  });

  it("every workflow navigate() call includes the /edit suffix", () => {
    source = readSource("NewWorkflowModal.tsx");
    const calls = extractWorkflowNavigateCalls(source);

    for (const call of calls) {
      expect(call, `Expected /edit suffix in: ${call}`).toMatch(/\/edit/);
    }
  });

  it("does NOT have any navigate() to bare /workflows/:id (without /edit)", () => {
    source = readSource("NewWorkflowModal.tsx");
    const barePattern = /navigate\(`\/workflows\/\$\{[^}]+\}`\)/g;
    const bareMatches = source.match(barePattern) ?? [];

    expect(
      bareMatches.length,
      `Found bare navigate() calls without /edit: ${bareMatches.join(", ")}`,
    ).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// 3. Route definition sanity — /workflows/:id/edit maps to CanvasPage
// ---------------------------------------------------------------------------

describe("Route config maps /workflows/:id/edit to CanvasPage", () => {
  it("/workflows/:id/edit route exists and loads CanvasPage", () => {
    const routesSource = readFileSync(
      resolve(FEATURES_DIR, "../../routes/index.tsx"),
      "utf-8",
    );

    // Should have a route definition for workflows/:id/edit
    expect(routesSource).toMatch(/path:\s*["']workflows\/:id\/edit["']/);

    // That route should import CanvasPage
    expect(routesSource).toMatch(/CanvasPage/);
  });
});
