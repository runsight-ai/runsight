import { readdirSync, readFileSync } from "node:fs";
import { extname, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { describe, expect, it } from "vitest";

const EXPECTED_MODES = [
  "workflow",
  "execution",
  "historical",
  "fork-draft",
] as const;

const GUI_SRC_ROOT = resolve(import.meta.dirname, "../../..");

type Mode = (typeof EXPECTED_MODES)[number];
type RegionName =
  | "topbar"
  | "center"
  | "palette"
  | "yaml"
  | "inspector"
  | "footer"
  | "statusBar";
type RegionState = { visible: boolean; editable: boolean };
type NormalizedModeConfig = {
  regions: Record<RegionName, RegionState>;
  actions: {
    save: boolean;
    run: boolean;
    fork: boolean;
    openWorkflow: boolean;
  };
  capabilities: {
    readOnly: boolean;
    usesRunOverlay: boolean;
    supportsSameSurfaceTransition: boolean;
    routeChangeRequired: boolean;
  };
};

const EXPECTED_MODE_MATRIX: Record<Mode, NormalizedModeConfig> = {
  workflow: {
    regions: {
      topbar: { visible: true, editable: true },
      center: { visible: true, editable: true },
      palette: { visible: true, editable: true },
      yaml: { visible: true, editable: true },
      inspector: { visible: true, editable: true },
      footer: { visible: true, editable: true },
      statusBar: { visible: true, editable: true },
    },
    actions: {
      save: true,
      run: true,
      fork: false,
      openWorkflow: false,
    },
    capabilities: {
      readOnly: false,
      usesRunOverlay: false,
      supportsSameSurfaceTransition: true,
      routeChangeRequired: false,
    },
  },
  execution: {
    regions: {
      topbar: { visible: true, editable: false },
      center: { visible: true, editable: false },
      palette: { visible: true, editable: false },
      yaml: { visible: true, editable: false },
      inspector: { visible: true, editable: false },
      footer: { visible: true, editable: false },
      statusBar: { visible: true, editable: false },
    },
    actions: {
      save: false,
      run: false,
      fork: false,
      openWorkflow: false,
    },
    capabilities: {
      readOnly: true,
      usesRunOverlay: true,
      supportsSameSurfaceTransition: true,
      routeChangeRequired: false,
    },
  },
  historical: {
    regions: {
      topbar: { visible: true, editable: false },
      center: { visible: true, editable: false },
      palette: { visible: false, editable: false },
      yaml: { visible: false, editable: false },
      inspector: { visible: true, editable: false },
      footer: { visible: true, editable: false },
      statusBar: { visible: true, editable: false },
    },
    actions: {
      save: false,
      run: false,
      fork: true,
      openWorkflow: true,
    },
    capabilities: {
      readOnly: true,
      usesRunOverlay: true,
      supportsSameSurfaceTransition: true,
      routeChangeRequired: false,
    },
  },
  "fork-draft": {
    regions: {
      topbar: { visible: true, editable: true },
      center: { visible: true, editable: true },
      palette: { visible: true, editable: true },
      yaml: { visible: true, editable: true },
      inspector: { visible: true, editable: true },
      footer: { visible: true, editable: true },
      statusBar: { visible: true, editable: true },
    },
    actions: {
      save: true,
      run: true,
      fork: false,
      openWorkflow: false,
    },
    capabilities: {
      readOnly: false,
      usesRunOverlay: false,
      supportsSameSurfaceTransition: true,
      routeChangeRequired: false,
    },
  },
};

function collectSourceFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const fullPath = resolve(dir, entry.name);

    if (entry.isDirectory()) {
      if (entry.name === "__tests__") {
        return [];
      }

      return collectSourceFiles(fullPath);
    }

    const extension = extname(entry.name);
    if (![".ts", ".tsx"].includes(extension) || entry.name.endsWith(".d.ts")) {
      return [];
    }

    return [fullPath];
  });
}

function isExpectedModeList(value: unknown): value is readonly string[] {
  return (
    Array.isArray(value)
    && value.length === EXPECTED_MODES.length
    && value.every((item) => typeof item === "string")
    && [...value].sort().join("|") === [...EXPECTED_MODES].sort().join("|")
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function candidateContractModules() {
  return collectSourceFiles(GUI_SRC_ROOT).filter((filePath) => {
    const source = readFileSync(filePath, "utf8");

    return (
      EXPECTED_MODES.every(
        (mode) => source.includes(`"${mode}"`) || source.includes(`'${mode}'`),
      )
      && source.includes("WorkflowSurfaceMode")
      && source.includes("WorkflowSurfaceProps")
      && /visible|editable|readOnly|usesRunOverlay|sameSurface/i.test(source)
    );
  });
}

async function loadContractModule() {
  const candidates = candidateContractModules();

  expect(candidates.length).toBeGreaterThan(0);

  for (const candidate of candidates) {
    const module = (await import(pathToFileURL(candidate).href)) as Record<
      string,
      unknown
    >;
    const modeList = findModeList(module);
    const modeConfig = findModeConfig(module);
    const lookup = findLookup(module, modeConfig);

    if (modeList && modeConfig && lookup) {
      return { candidate, source: readFileSync(candidate, "utf8"), modeList, modeConfig, lookup };
    }
  }

  throw new Error("Expected at least one GUI source module to export a workflow surface runtime contract");
}

function exportedValues(module: Record<string, unknown>) {
  const values = Object.values(module);
  const defaultValue = module.default;

  if (isRecord(defaultValue)) {
    values.push(...Object.values(defaultValue));
  }

  return values;
}

function findModeList(module: Record<string, unknown>) {
  return exportedValues(module).find(isExpectedModeList) as
    | readonly string[]
    | undefined;
}

function findModeConfig(module: Record<string, unknown>) {
  return exportedValues(module).find((value) => {
    if (!isRecord(value)) {
      return false;
    }

    return EXPECTED_MODES.every((mode) => mode in value && isRecord(value[mode]));
  }) as Record<Mode, Record<string, unknown>> | undefined;
}

function findLookup(
  module: Record<string, unknown>,
  modeConfig: Record<Mode, Record<string, unknown>> | undefined,
) {
  if (!modeConfig) {
    return undefined;
  }

  return exportedValues(module).find((value) => {
    if (typeof value !== "function") {
      return false;
    }

    return EXPECTED_MODES.every((mode) => {
      try {
        return value(mode) === modeConfig[mode];
      } catch {
        return false;
      }
    });
  }) as ((mode: Mode) => Record<string, unknown>) | undefined;
}

function getBranch(
  container: Record<string, unknown>,
  keys: string[],
): Record<string, unknown> {
  for (const key of keys) {
    const value = container[key];
    if (isRecord(value)) {
      return value;
    }
  }

  throw new Error(`Missing expected branch: ${keys.join(" | ")}`);
}

function getBoolean(
  container: Record<string, unknown>,
  keys: string[],
): boolean {
  for (const key of keys) {
    const value = container[key];
    if (typeof value === "boolean") {
      return value;
    }
  }

  throw new Error(`Missing expected boolean: ${keys.join(" | ")}`);
}

function normalizeModeConfig(config: Record<string, unknown>): NormalizedModeConfig {
  const regionContainer = getBranch(config, ["regions", "sections"]);
  const actions = getBranch(config, ["actions"]);
  const capabilities = getBranch(config, ["capabilities"]);

  return {
    regions: {
      topbar: normalizeRegion(getBranch(regionContainer, ["topbar"])),
      center: normalizeRegion(getBranch(regionContainer, ["center", "centerSurface"])),
      palette: normalizeRegion(getBranch(regionContainer, ["palette"])),
      yaml: normalizeRegion(getBranch(regionContainer, ["yaml"])),
      inspector: normalizeRegion(getBranch(regionContainer, ["inspector"])),
      footer: normalizeRegion(getBranch(regionContainer, ["footer"])),
      statusBar: normalizeRegion(getBranch(regionContainer, ["statusBar", "status_bar"])),
    },
    actions: {
      save: getBoolean(actions, ["save"]),
      run: getBoolean(actions, ["run"]),
      fork: getBoolean(actions, ["fork"]),
      openWorkflow: getBoolean(actions, ["openWorkflow", "open_workflow"]),
    },
    capabilities: {
      readOnly: getBoolean(capabilities, ["readOnly", "read_only"]),
      usesRunOverlay: getBoolean(capabilities, ["usesRunOverlay", "uses_run_overlay"]),
      supportsSameSurfaceTransition: getBoolean(capabilities, [
        "supportsSameSurfaceTransition",
        "supports_same_surface_transition",
      ]),
      routeChangeRequired: getBoolean(capabilities, [
        "routeChangeRequired",
        "route_change_required",
      ]),
    },
  };
}

function normalizeRegion(region: Record<string, unknown>): RegionState {
  return {
    visible: getBoolean(region, ["visible"]),
    editable: getBoolean(region, ["editable"]),
  };
}

describe("RUN-591 workflow surface contract", () => {
  it("defines WorkflowSurfaceMode and WorkflowSurfaceProps in a GUI runtime contract module without requiring one exact filename", async () => {
    const { source } = await loadContractModule();

    expect(source).toMatch(
      /type\s+WorkflowSurfaceMode\s*=\s*"workflow"\s*\|\s*"execution"\s*\|\s*"historical"\s*\|\s*"fork-draft"/,
    );
    expect(source).toMatch(/interface\s+WorkflowSurfaceProps/);
    expect(source).toMatch(/workflowId\??:\s*string/);
    expect(source).toMatch(/runId\??:\s*string/);
    expect(source).toMatch(/initialMode:\s*WorkflowSurfaceMode/);
  });

  it("exports a canonical runtime mode list, config map, and lookup helper without fixing one exact export spelling", async () => {
    const { modeList, modeConfig, lookup } = await loadContractModule();

    expect(modeList).toEqual(EXPECTED_MODES);
    expect(Object.keys(modeConfig)).toEqual(EXPECTED_MODES);

    for (const mode of EXPECTED_MODES) {
      expect(lookup(mode)).toBe(modeConfig[mode]);
    }
  });

  it("locks the explicit per-mode truth table for sections, actions, and capabilities", async () => {
    const { modeConfig } = await loadContractModule();

    for (const mode of EXPECTED_MODES) {
      expect(normalizeModeConfig(modeConfig[mode])).toEqual(
        EXPECTED_MODE_MATRIX[mode],
      );
    }
  });

  it("keeps execution on the live workflow-edit surface instead of allowing a separate-page placeholder contract", async () => {
    const { modeConfig } = await loadContractModule();
    const workflow = normalizeModeConfig(modeConfig.workflow);
    const execution = normalizeModeConfig(modeConfig.execution);

    expect(execution.capabilities.routeChangeRequired).toBe(false);
    expect(execution.capabilities.supportsSameSurfaceTransition).toBe(true);
    expect(execution.capabilities.usesRunOverlay).toBe(true);
    expect(execution.regions.palette).toEqual({ visible: true, editable: false });
    expect(execution.regions.yaml).toEqual({ visible: true, editable: false });
    expect(execution.actions).toEqual(EXPECTED_MODE_MATRIX.execution.actions);
    expect(execution.actions).not.toEqual(workflow.actions);
    expect(execution.actions).not.toEqual({
      save: true,
      run: true,
      fork: true,
      openWorkflow: true,
    });
  });

  it("keeps historical mode read-only and makes fork-draft the editing transition on the same surface", async () => {
    const { modeConfig } = await loadContractModule();
    const historical = normalizeModeConfig(modeConfig.historical);
    const forkDraft = normalizeModeConfig(modeConfig["fork-draft"]);

    expect(historical).toEqual(EXPECTED_MODE_MATRIX.historical);
    expect(forkDraft).toEqual(EXPECTED_MODE_MATRIX["fork-draft"]);
    expect(historical.regions.palette).toEqual({ visible: false, editable: false });
    expect(historical.regions.yaml).toEqual({ visible: false, editable: false });
    expect(forkDraft.regions.palette).toEqual({ visible: true, editable: true });
    expect(forkDraft.regions.yaml).toEqual({ visible: true, editable: true });
    expect(forkDraft.capabilities.routeChangeRequired).toBe(false);
    expect(forkDraft.capabilities.supportsSameSurfaceTransition).toBe(true);
  });
});
