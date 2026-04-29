import { existsSync, readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const runsSource = readFileSync(new URL("../runs.ts", import.meta.url), "utf8");
const workflowsSource = readFileSync(new URL("../workflows.ts", import.meta.url), "utf8");
const localRegressionSchemaUrl = new URL("../../types/schemas/regressions.ts", import.meta.url);
const localRegressionSchemaExists = existsSync(localRegressionSchemaUrl);
const localRegressionSchemaSource = localRegressionSchemaExists
  ? readFileSync(localRegressionSchemaUrl, "utf8")
  : "";
const regressionBadgeUtilsSource = readFileSync(
  new URL("../../features/workflows/regressionBadge.utils.ts", import.meta.url),
  "utf8",
);
const surfaceBottomPanelSource = readFileSync(
  new URL("../../features/surface/SurfaceBottomPanel.tsx", import.meta.url),
  "utf8",
);

describe("GUI regression contracts come from @runsight/shared/zod", () => {
  it("runs.ts parses run regressions with the shared schema instead of a local z.object", () => {
    const getRunRegressionsBlock = runsSource.match(
      /getRunRegressions[\s\S]*?(?=\n {2}\w|\n\};)/,
    )?.[0];

    expect(getRunRegressionsBlock).toBeTruthy();
    expect(runsSource).toMatch(/RunRegressionsResponseSchema/);
    expect(runsSource).toMatch(/@runsight\/shared\/zod/);
    expect(getRunRegressionsBlock).toContain("RunRegressionsResponseSchema.parse");
    expect(runsSource).not.toMatch(/export const RunRegressionSchema/);
    expect(runsSource).not.toMatch(/export const RunRegressionsResponseSchema/);
  });

  it("workflows.ts parses workflow regressions with the shared schema instead of the local schema module", () => {
    const getWorkflowRegressionsBlock = workflowsSource.match(
      /getWorkflowRegressions[\s\S]*?(?=\n {2}\w|\n\};)/,
    )?.[0];

    expect(getWorkflowRegressionsBlock).toBeTruthy();
    expect(workflowsSource).toMatch(/WorkflowRegressionsResponseSchema/);
    expect(workflowsSource).toMatch(/@runsight\/shared\/zod/);
    expect(getWorkflowRegressionsBlock).toContain("WorkflowRegressionsResponseSchema.parse");
    expect(workflowsSource).not.toContain("../types/schemas/regressions");
  });

  it("local regression schema module no longer defines canonical regression response schemas", () => {
    if (!localRegressionSchemaExists) {
      expect(localRegressionSchemaExists).toBe(false);
      return;
    }

    expect(localRegressionSchemaSource).not.toMatch(/export const WorkflowRegressionSchema/);
    expect(localRegressionSchemaSource).not.toMatch(/export const WorkflowRegressionsResponseSchema/);
  });

  it("production GUI consumers stop importing regression contracts from the local schema path", () => {
    expect(regressionBadgeUtilsSource).not.toContain("types/schemas/regressions");
    expect(surfaceBottomPanelSource).not.toContain("types/schemas/regressions");
  });
});
