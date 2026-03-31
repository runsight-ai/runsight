import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const SRC_DIR = resolve(__dirname, "..", "..");
const DASHBOARD_PATH = resolve(SRC_DIR, "features", "dashboard", "DashboardOrOnboarding.tsx");
const RUN_DETAIL_HEADER_PATH = resolve(SRC_DIR, "features", "runs", "RunDetailHeader.tsx");

function readSource(filePath: string): string {
  return readFileSync(filePath, "utf-8");
}

describe("RUN-431 dashboard list-navigation cleanup", () => {
  it('sends the "Open Flows" CTA directly to /flows', () => {
    const source = readSource(DASHBOARD_PATH);

    expect(source).toMatch(/["']Open Flows["']/);
    expect(source).toMatch(/navigate\(\s*["'`]\/flows["'`]\s*\)/);
    expect(source).not.toMatch(/navigate\(\s*["'`]\/workflows["'`]\s*\)/);
  });

  it('sends the attention overflow "see all" action directly to /flows?tab=runs', () => {
    const source = readSource(DASHBOARD_PATH);

    expect(source).toMatch(/see all/i);
    expect(source).toMatch(/navigate\(\s*["'`]\/flows\?tab=runs["'`]\s*\)/);
    expect(source).not.toMatch(/navigate\(\s*["'`]\/runs["'`]\s*\)/);
  });
});

describe("RUN-431 run detail list-navigation cleanup", () => {
  it('links the "Back to runs" affordance to /flows?tab=runs', () => {
    const source = readSource(RUN_DETAIL_HEADER_PATH);

    expect(source).toMatch(/Back to runs/);
    expect(source).toMatch(/to=["']\/flows\?tab=runs["']/);
    expect(source).not.toMatch(/to=["']\/runs["']/);
  });
});
