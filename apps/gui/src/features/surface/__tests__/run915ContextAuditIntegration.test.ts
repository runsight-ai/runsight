import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const GUI_SRC = "/Users/nataly/Documents/github/runsight/apps/gui/src";
const bottomPanelSource = readFileSync(
  resolve(GUI_SRC, "features", "surface", "SurfaceBottomPanel.tsx"),
  "utf8",
);
const workflowSurfaceSource = readFileSync(
  resolve(GUI_SRC, "features", "surface", "WorkflowSurface.tsx"),
  "utf8",
);
const runsQuerySource = readFileSync(resolve(GUI_SRC, "queries", "runs.ts"), "utf8");
const runsApiSource = readFileSync(resolve(GUI_SRC, "api", "runs.ts"), "utf8");

describe("RUN-915 context audit integration guard", () => {
  it("runsApi keeps using generated ContextAuditListResponseSchema", () => {
    expect(runsApiSource).toContain("@runsight/shared/zod");
    expect(runsApiSource).toContain("ContextAuditListResponseSchema");
    expect(runsApiSource).toContain("getRunContextAudit");

    const method = runsApiSource.match(/getRunContextAudit[\s\S]*?(?=\n {2}\w|\n\};)/);
    expect(method).not.toBeNull();
    expect(method?.[0]).toContain("ContextAuditListResponseSchema.parse");
  });

  it("query layer imports generated schemas and does not hand-write backend audit schemas", () => {
    expect(runsQuerySource).toContain("@runsight/shared/zod");
    expect(runsQuerySource).toContain("ContextAuditEventV1Schema");
    expect(runsQuerySource).not.toMatch(/ContextAudit(Event|Record|List).*=\s*z\.object/);
  });

  it("bottom panel or workflow surface loads historical audit and subscribes to live audit", () => {
    const ownerSource = `${bottomPanelSource}\n${workflowSurfaceSource}`;

    expect(ownerSource).toMatch(/useRunContextAudit\b/);
    expect(ownerSource).toMatch(/useRunContextAuditStream\b/);
    expect(ownerSource).not.toMatch(/context_resolution[\s\S]{0,120}replay/);
  });
});
