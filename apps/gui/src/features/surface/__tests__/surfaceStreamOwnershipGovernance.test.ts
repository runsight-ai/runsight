/**
 * Governance: readonly/bottom-panel run-stream ownership boundary.
 *
 * Owner: GUI Surface.
 * Boundary: SurfaceBottomPanel owns selected-run stream ownership, audit
 * hydration, stale-stream ignoring, log replay/history normalization, run
 * switching, and terminal-event stream closure. WorkflowSurface readonly
 * integration owns readonly hydration, inspector/audit bridge, fork routing,
 * and edit-vs-readonly guards only.
 * Exit criteria: remove this source governance once the stream-owner split is
 * enforced by a typed package-local GUI surface test helper and suite ownership
 * checks that cannot drift back into duplicated inline harnesses.
 */

import { describe, expect, it } from "vitest";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

const SURFACE_TEST_DIR = __dirname;
const SURFACE_HELPERS_DIR = resolve(SURFACE_TEST_DIR, "helpers");
const READONLY_SUITE = resolve(SURFACE_TEST_DIR, "readonlySurfaceIntegration.test.tsx");
const BOTTOM_PANEL_SUITE = resolve(SURFACE_TEST_DIR, "bottomPanelControllers.test.tsx");

function readSuite(path: string): string {
  return readFileSync(path, "utf-8");
}

function exportedHelperSources(): string[] {
  if (!existsSync(SURFACE_HELPERS_DIR)) {
    return [];
  }

  return readdirSync(SURFACE_HELPERS_DIR)
    .filter((fileName) => /\.[cm]?tsx?$/.test(fileName))
    .map((fileName) => readFileSync(resolve(SURFACE_HELPERS_DIR, fileName), "utf-8"));
}

function matchingLines(source: string, pattern: RegExp): string[] {
  return source
    .split("\n")
    .map((line, index) => ({ line, index }))
    .filter(({ line }) => pattern.test(line))
    .map(({ line, index }) => `${index + 1}: ${line.trim()}`);
}

describe("Governance: readonly/bottom-panel run-stream ownership boundary", () => {
  it("keeps selected-run stream ownership assertions in the bottom-panel controller suite", () => {
    const bottomPanelSource = readSuite(BOTTOM_PANEL_SUITE);

    expect(bottomPanelSource).toContain(
      "keeps audit hydration attached to the selected run from one shared stream",
    );
    expect(bottomPanelSource).toContain(
      "switches runs by closing the prior shared stream and ignoring stale log and audit events",
    );
    expect(bottomPanelSource).toContain(
      "closes the shared stream on terminal events while keeping audit data, logs, and canvas updates in sync",
    );
  });

  it("keeps readonly integration free of bottom-panel stream-owner invariants", () => {
    const readonlySource = readSuite(READONLY_SUITE);
    const forbiddenReadonlyOwnership = matchingLines(
      readonlySource,
      /shared stream owner|eventSources\[\d+\]\?\.emit\("run_completed"|new EventSource\(`\/api\/runs\/\$\{runId\}\/stream`\)|addEventListener\("run_completed"|addEventListener\("run_failed"/,
    );

    expect(forbiddenReadonlyOwnership).toEqual([]);
  });

  it("uses a package-local GUI surface test helper for shared run stream and audit builders", () => {
    const helperSources = exportedHelperSources();
    const hasStreamHelper = helperSources.some(
      (source) =>
        /export\s+(?:class|function|const)\s+\w*EventSource\w*/.test(source) &&
        /addEventListener/.test(source),
    );
    const hasRunBuilder = helperSources.some((source) =>
      /export\s+function\s+(?:build|make)\w*Run\b/.test(source),
    );
    const hasWorkflowBuilder = helperSources.some((source) =>
      /export\s+function\s+(?:build|make)\w*Workflow\b/.test(source),
    );
    const hasAuditBuilder = helperSources.some((source) =>
      /export\s+function\s+(?:build|make)\w*(?:ContextAudit|Audit)\w*Event\b/.test(source),
    );

    expect({
      hasStreamHelper,
      hasRunBuilder,
      hasWorkflowBuilder,
      hasAuditBuilder,
    }).toEqual({
      hasStreamHelper: true,
      hasRunBuilder: true,
      hasWorkflowBuilder: true,
      hasAuditBuilder: true,
    });
  });

  it("does not keep duplicate inline EventSource/run/workflow/audit builders in both suites", () => {
    const readonlySource = readSuite(READONLY_SUITE);
    const bottomPanelSource = readSuite(BOTTOM_PANEL_SUITE);

    const readonlyInlineBuilders = matchingLines(
      readonlySource,
      /^(class MockEventSource|function build(?:Run|Workflow|ContextAuditEvent)\b)/,
    );
    const bottomPanelInlineBuilders = matchingLines(
      bottomPanelSource,
      /^(class MockEventSource|function make(?:Run|ContextResolutionEvent)\b)/,
    );

    expect({
      readonlyInlineBuilders,
      bottomPanelInlineBuilders,
    }).toEqual({
      readonlyInlineBuilders: [],
      bottomPanelInlineBuilders: [],
    });
  });
});
