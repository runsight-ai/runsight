import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const CONTRACT_PATH = resolve(
  import.meta.dirname,
  "../workflowSurfaceContract.ts",
);

async function importContract() {
  return import("../workflowSurfaceContract");
}

describe("RUN-591 workflow surface contract", () => {
  it("defines WorkflowSurfaceMode as the canonical four-mode union and colocates it with a runtime contract module", () => {
    expect(existsSync(CONTRACT_PATH)).toBe(true);

    const source = readFileSync(CONTRACT_PATH, "utf8");

    expect(source).toMatch(
      /export\s+type\s+WorkflowSurfaceMode\s*=\s*"workflow"\s*\|\s*"execution"\s*\|\s*"historical"\s*\|\s*"fork-draft"/,
    );
    expect(source).toMatch(/WORKFLOW_SURFACE_MODES/);
    expect(source).toMatch(/WORKFLOW_SURFACE_MODE_CONFIG/);
    expect(source).toMatch(/getWorkflowSurfaceModeConfig/);
  });

  it("defines WorkflowSurfaceProps so the shared surface can accept workflow and run identities without forcing both", () => {
    expect(existsSync(CONTRACT_PATH)).toBe(true);

    const source = readFileSync(CONTRACT_PATH, "utf8");

    expect(source).toMatch(/export\s+interface\s+WorkflowSurfaceProps/);
    expect(source).toMatch(/workflowId\??:\s*string/);
    expect(source).toMatch(/runId\??:\s*string/);
    expect(source).toMatch(/initialMode:\s*WorkflowSurfaceMode/);
    expect(source).toMatch(/hasRunOverlay\??:\s*boolean/);
    expect(source).toMatch(/isEditable\??:\s*boolean/);
  });

  it("exports a canonical runtime mode list, config map, and lookup helper", async () => {
    const contract = await importContract();

    expect(contract.WORKFLOW_SURFACE_MODES).toEqual([
      "workflow",
      "execution",
      "historical",
      "fork-draft",
    ]);
    expect(Object.keys(contract.WORKFLOW_SURFACE_MODE_CONFIG)).toEqual(
      contract.WORKFLOW_SURFACE_MODES,
    );
    expect(typeof contract.getWorkflowSurfaceModeConfig).toBe("function");
    expect(contract.getWorkflowSurfaceModeConfig("workflow")).toEqual(
      contract.WORKFLOW_SURFACE_MODE_CONFIG.workflow,
    );
  });

  it("makes visibility explicit for topbar, center, palette, yaml, inspector, footer, and status bar in every mode", async () => {
    const { WORKFLOW_SURFACE_MODE_CONFIG } = await importContract();

    for (const mode of [
      "workflow",
      "execution",
      "historical",
      "fork-draft",
    ] as const) {
      expect(WORKFLOW_SURFACE_MODE_CONFIG[mode]).toMatchObject({
        sections: {
          topbar: { visible: expect.any(Boolean) },
          center: { visible: expect.any(Boolean) },
          palette: { visible: expect.any(Boolean) },
          yaml: { visible: expect.any(Boolean) },
          inspector: { visible: expect.any(Boolean) },
          footer: { visible: expect.any(Boolean) },
          statusBar: { visible: expect.any(Boolean) },
        },
      });
    }
  });

  it("defines the per-mode action and capability surface so later tickets do not reinvent behavior ad hoc", async () => {
    const { WORKFLOW_SURFACE_MODE_CONFIG } = await importContract();

    for (const mode of [
      "workflow",
      "execution",
      "historical",
      "fork-draft",
    ] as const) {
      expect(WORKFLOW_SURFACE_MODE_CONFIG[mode]).toMatchObject({
        actions: {
          save: expect.any(Boolean),
          run: expect.any(Boolean),
          fork: expect.any(Boolean),
          openWorkflow: expect.any(Boolean),
        },
        capabilities: {
          readOnly: expect.any(Boolean),
          usesRunOverlay: expect.any(Boolean),
          supportsSameSurfaceTransition: expect.any(Boolean),
        },
      });
    }
  });

  it("locks the clarified runtime invariants for workflow, execution, historical, and fork-draft", async () => {
    const { WORKFLOW_SURFACE_MODE_CONFIG } = await importContract();

    expect(WORKFLOW_SURFACE_MODE_CONFIG.workflow.capabilities).toMatchObject({
      readOnly: false,
      usesRunOverlay: false,
      supportsSameSurfaceTransition: true,
    });

    expect(WORKFLOW_SURFACE_MODE_CONFIG.execution.capabilities).toMatchObject({
      usesRunOverlay: true,
      supportsSameSurfaceTransition: true,
    });

    expect(WORKFLOW_SURFACE_MODE_CONFIG.historical.capabilities).toMatchObject({
      readOnly: true,
      usesRunOverlay: true,
      supportsSameSurfaceTransition: true,
    });

    expect(
      WORKFLOW_SURFACE_MODE_CONFIG["fork-draft"].capabilities,
    ).toMatchObject({
      readOnly: false,
      supportsSameSurfaceTransition: true,
    });
  });

  it("models the edge cases that anchor this epic: workflow without overlay, historical read-only state, and fork-draft route changes without a surface swap", async () => {
    const { WORKFLOW_SURFACE_MODE_CONFIG } = await importContract();

    expect(WORKFLOW_SURFACE_MODE_CONFIG.workflow.capabilities.usesRunOverlay).toBe(
      false,
    );
    expect(WORKFLOW_SURFACE_MODE_CONFIG.historical.capabilities.readOnly).toBe(
      true,
    );
    expect(
      WORKFLOW_SURFACE_MODE_CONFIG["fork-draft"].capabilities
        .supportsSameSurfaceTransition,
    ).toBe(true);
  });
});
