/**
 * Regression checks for the bottom-panel SSE/log controller wiring.
 *
 * The SSE ownership now lives in `useSurfaceBottomPanelLogs`, while
 * `SurfaceBottomPanel` consumes the hook and renders the resulting entries.
 * These source-level checks keep the original RUN-371 contract covered at the
 * current seam.
 */

import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const SRC_DIR = resolve(__dirname, "../../..");
const PANEL_PATH = "features/surface/SurfaceBottomPanel.tsx";
const LOGS_HOOK_PATH = "features/surface/useSurfaceBottomPanelLogs.ts";

function readSource(relativePath: string): string {
  return readFileSync(resolve(SRC_DIR, relativePath), "utf-8");
}

describe("SurfaceBottomPanel SSE wiring", () => {
  it("renders log entries from useSurfaceBottomPanelLogs", () => {
    const panelSource = readSource(PANEL_PATH);
    expect(panelSource).toMatch(/useSurfaceBottomPanelLogs/);
    expect(panelSource).toMatch(/entries\.length === 0/);
    expect(panelSource).toMatch(/entries\.map/);
  });

  it("creates the EventSource from the selected run stream endpoint", () => {
    const hookSource = readSource(LOGS_HOOK_PATH);
    expect(hookSource).toMatch(/new\s+EventSource\(`\/api\/runs\/\$\{runId\}\/stream`\)/);
    expect(hookSource).toMatch(/useEffect/);
  });

  it("clears live entries when the inspected run changes", () => {
    const hookSource = readSource(LOGS_HOOK_PATH);
    expect(hookSource).toMatch(/setLiveEntries\(\[\]\)/);
    expect(hookSource).toMatch(/\}, \[runId\]\)/);
  });

  it("handles live log_entry, replay, and node lifecycle event types", () => {
    const hookSource = readSource(LOGS_HOOK_PATH);
    expect(hookSource).toMatch(/"log_entry"/);
    expect(hookSource).toMatch(/"replay"/);
    expect(hookSource).toMatch(/"node_started"/);
    expect(hookSource).toMatch(/"node_completed"/);
    expect(hookSource).toMatch(/"node_failed"/);
  });

  it("maps SSE progress into timestamped level/message log rows", () => {
    const hookSource = readSource(LOGS_HOOK_PATH);
    expect(hookSource).toMatch(/level:\s*"info"/);
    expect(hookSource).toMatch(/level:\s*"error"/);
    expect(hookSource).toMatch(/message:\s*`Node/);
    expect(hookSource).toMatch(/message:\s*`Run failed/);
  });

  it("avoids replay duplication when fetched history already exists", () => {
    const hookSource = readSource(LOGS_HOOK_PATH);
    expect(hookSource).toMatch(/hasFetchedHistoryRef/);
    expect(hookSource).toMatch(/if \(hasFetchedHistoryRef\.current\)/);
  });

  it("closes EventSource on terminal events and on effect cleanup", () => {
    const hookSource = readSource(LOGS_HOOK_PATH);
    expect(hookSource).toMatch(/eventType === "run_completed" \|\| eventType === "run_failed"/);
    expect(hookSource).toMatch(/source\.close\(\)/);
    expect(hookSource).toMatch(/return \(\) => \{/);
  });

  it("keeps store updates routed through mapSSEEventToStoreAction", () => {
    const hookSource = readSource(LOGS_HOOK_PATH);
    expect(hookSource).toMatch(/mapSSEEventToStoreAction/);
    expect(hookSource).toMatch(/setNodeStatus/);
    expect(hookSource).toMatch(/setActiveRunId/);
  });
});
