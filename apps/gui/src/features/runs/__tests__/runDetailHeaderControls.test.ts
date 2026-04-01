import { describe, expect, it } from "vitest";
import { readFileSync } from "fs";
import { resolve } from "path";

const RUN_DETAIL_HEADER_SOURCE = readFileSync(
  resolve(__dirname, "../RunDetailHeader.tsx"),
  "utf-8",
);

describe("Run detail header controls (RUN-510)", () => {
  it("keeps the back control wired to the runs list", () => {
    expect(RUN_DETAIL_HEADER_SOURCE).toMatch(/<Link\s+to="\/runs">/);
    expect(RUN_DETAIL_HEADER_SOURCE).toMatch(/aria-label="Back to runs"/);
  });

  it("uses an honest Open Workflow label when the primary action opens the workflow", () => {
    expect(RUN_DETAIL_HEADER_SOURCE).toMatch(/navigate\(`\/workflows\/\$\{run\.workflow_id\}`\)/);
    expect(RUN_DETAIL_HEADER_SOURCE).toMatch(/>\s*Open Workflow\s*</);
    expect(RUN_DETAIL_HEADER_SOURCE).not.toMatch(/>\s*Run Again\s*</);
  });

  it("does not switch to a misleading Retry label for failed runs when the action still opens the workflow", () => {
    expect(RUN_DETAIL_HEADER_SOURCE).toMatch(/navigate\(`\/workflows\/\$\{run\.workflow_id\}`\)/);
    expect(RUN_DETAIL_HEADER_SOURCE).not.toMatch(/>\s*Retry\s*</);
  });

  it("removes the standalone header zoom controls instead of showing dead affordances", () => {
    expect(RUN_DETAIL_HEADER_SOURCE).not.toMatch(/aria-label="Canvas zoom controls"/);
    expect(RUN_DETAIL_HEADER_SOURCE).not.toMatch(/aria-label="Zoom in"/);
    expect(RUN_DETAIL_HEADER_SOURCE).not.toMatch(/aria-label="Zoom out"/);
    expect(RUN_DETAIL_HEADER_SOURCE).not.toMatch(/aria-label="Fit to screen"/);
    expect(RUN_DETAIL_HEADER_SOURCE).not.toMatch(/\bZoomIn\b/);
    expect(RUN_DETAIL_HEADER_SOURCE).not.toMatch(/\bZoomOut\b/);
    expect(RUN_DETAIL_HEADER_SOURCE).not.toMatch(/\bMaximize\b/);
  });
});
