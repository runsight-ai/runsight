/**
 * Governance: GUI screen design-token boundary sweep.
 *
 * Owner: GUI design-token migration governance.
 * Boundary: this suite statically inspects shipped GUI screen-adjacent source
 * for retired shadcn/Tailwind token names and retired CSS var() references. It
 * intentionally avoids production imports, runtime state, user config, network
 * calls, and broad feature behavior assertions.
 * Exit criteria: delete this suite after the GUI token migration is complete,
 * retired token names are blocked by lint/codegen, and the protected live/dead
 * screen file lists are owned by the replacement boundary.
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const SRC_DIR = resolve(__dirname, "../..");

type FileGroup = {
  name: string;
  files: string[];
};

type TokenDetector = {
  name: string;
  kind: "tailwind" | "var";
  pattern: RegExp;
  safeSamples?: string[];
};

const FILE_GROUPS: FileGroup[] = [
  {
    name: "shared components",
    files: [
      "components/shared/DataTable.tsx",
      "components/shared/DeleteConfirmDialog.tsx",
      "components/shared/ErrorBoundary.tsx",
      "components/shared/PageHeader.tsx",
      "components/shared/StatusBadge.tsx",
    ],
  },
  {
    name: "provider components",
    files: ["components/provider/ProviderSetup.tsx"],
  },
  {
    name: "canvas features",
    files: [
      "features/surface/SurfaceCanvas.tsx",
      "features/surface/nodes/SoulNode.tsx",
      "features/surface/nodes/StartNode.tsx",
    ],
  },
  {
    name: "runs features",
    files: [
      "features/surface/SurfaceInspectorPanel.tsx",
      "features/surface/WorkflowSurface.tsx",
      "features/surface/surfaceUtils.ts",
    ],
  },
  {
    name: "settings features",
    files: [
      "features/settings/ModelsTab.tsx",
      "features/settings/ProvidersTab.tsx",
      "features/settings/SettingsPage.tsx",
    ],
  },
  {
    name: "other feature pages",
    files: ["features/dashboard/DashboardOrOnboarding.tsx"],
  },
  {
    name: "layouts",
    files: ["routes/layouts/ShellLayout.tsx"],
  },
  {
    name: "utilities",
    files: ["utils/icons.tsx"],
  },
];

const ALL_FILES = FILE_GROUPS.flatMap((group) => group.files);

const PROTECTED_LIVE_FILES = [
  "components/shared/DeleteConfirmDialog.tsx",
  "components/shared/StatusBadge.tsx",
  "components/provider/ProviderSetup.tsx",
];

const RETIRED_FILES = [
  "components/shared/CrudListPage.tsx",
  "features/health/HealthPage.tsx",
  "features/workflows/NewWorkflowModal.tsx",
  "features/sidebar/SoulList.tsx",
  "features/sidebar/SoulModals.tsx",
  "features/sidebar/TaskModals.tsx",
  "features/sidebar/StepModals.tsx",
];

const TOKEN_DETECTORS: TokenDetector[] = [
  { kind: "tailwind", name: "bg-background", pattern: /\bbg-background\b/ },
  { kind: "tailwind", name: "bg-card", pattern: /\bbg-card\b/ },
  { kind: "tailwind", name: "bg-popover", pattern: /\bbg-popover\b/ },
  {
    kind: "tailwind",
    name: "bg-primary",
    pattern: /\bbg-primary(?!-foreground\b)(?![\w-])/,
    safeSamples: ["bg-primary-foreground"],
  },
  {
    kind: "tailwind",
    name: "bg-secondary",
    pattern: /\bbg-secondary(?!-foreground\b)(?![\w-])/,
    safeSamples: ["bg-secondary-foreground"],
  },
  {
    kind: "tailwind",
    name: "bg-muted",
    pattern: /\bbg-muted(?!-foreground\b)(?![\w-])/,
    safeSamples: ["bg-muted-foreground"],
  },
  {
    kind: "tailwind",
    name: "bg-accent",
    pattern: /\bbg-accent(?!-foreground\b)(?![\w-])/,
    safeSamples: ["bg-accent-foreground"],
  },
  { kind: "tailwind", name: "bg-destructive", pattern: /\bbg-destructive(?![\w-])/ },
  { kind: "tailwind", name: "text-foreground", pattern: /\btext-foreground(?![\w-])/ },
  { kind: "tailwind", name: "text-primary-foreground", pattern: /\btext-primary-foreground\b/ },
  { kind: "tailwind", name: "text-muted-foreground", pattern: /\btext-muted-foreground\b/ },
  { kind: "tailwind", name: "text-card-foreground", pattern: /\btext-card-foreground\b/ },
  { kind: "tailwind", name: "text-popover-foreground", pattern: /\btext-popover-foreground\b/ },
  { kind: "tailwind", name: "text-secondary-foreground", pattern: /\btext-secondary-foreground\b/ },
  { kind: "tailwind", name: "text-accent-foreground", pattern: /\btext-accent-foreground\b/ },
  { kind: "tailwind", name: "text-destructive", pattern: /\btext-destructive(?![\w-])/ },
  {
    kind: "tailwind",
    name: "border-border",
    pattern:
      /\bborder-border(?!-default\b)(?!-focus\b)(?!-hover\b)(?!-accent\b)(?!-danger\b)(?!-success\b)(?!-warning\b)(?!-info\b)(?!-subtle\b)(?![\w-])/,
    safeSamples: [
      "border-border-default",
      "border-border-focus",
      "border-border-hover",
      "border-border-accent",
      "border-border-danger",
      "border-border-success",
      "border-border-warning",
      "border-border-info",
      "border-border-subtle",
    ],
  },
  { kind: "tailwind", name: "border-input", pattern: /\bborder-input(?![\w-])/ },
  { kind: "tailwind", name: "ring-ring", pattern: /\bring-ring(?![\w-])/ },
  { kind: "var", name: "var(--background)", pattern: /var\(--background\)/ },
  { kind: "var", name: "var(--foreground)", pattern: /var\(--foreground\)/ },
  {
    kind: "var",
    name: "var(--primary)",
    pattern: /var\(--primary\)/,
    safeSamples: ["var(--primary-hover)", "var(--primary-12)"],
  },
  {
    kind: "var",
    name: "var(--border)",
    pattern: /var\(--border\)/,
    safeSamples: ["var(--border-default)"],
  },
  { kind: "var", name: "var(--card)", pattern: /var\(--card\)/ },
  {
    kind: "var",
    name: "var(--muted)",
    pattern: /var\(--muted\)/,
    safeSamples: ["var(--muted-subtle)"],
  },
  { kind: "var", name: "var(--ring)", pattern: /var\(--ring\)/ },
  { kind: "var", name: "var(--destructive)", pattern: /var\(--destructive\)/ },
  { kind: "var", name: "var(--input)", pattern: /var\(--input\)/ },
  { kind: "var", name: "var(--primary-hover)", pattern: /var\(--primary-hover\)/ },
  { kind: "var", name: "var(--primary-05)", pattern: /var\(--primary-05\)/ },
  { kind: "var", name: "var(--primary-08)", pattern: /var\(--primary-08\)/ },
  { kind: "var", name: "var(--primary-10)", pattern: /var\(--primary-10\)/ },
  { kind: "var", name: "var(--primary-12)", pattern: /var\(--primary-12\)/ },
  { kind: "var", name: "var(--muted-subtle)", pattern: /var\(--muted-subtle\)/ },
  {
    kind: "var",
    name: "var(--surface)",
    pattern: /var\(--surface\)/,
    safeSamples: ["var(--surface-primary)", "var(--surface-secondary)"],
  },
  { kind: "var", name: "var(--surface-elevated)", pattern: /var\(--surface-elevated\)/ },
  {
    kind: "var",
    name: "var(--error)",
    pattern: /var\(--error\)/,
    safeSamples: ["var(--error-hover)"],
  },
  { kind: "var", name: "var(--error-hover)", pattern: /var\(--error-hover\)/ },
  { kind: "var", name: "var(--success)", pattern: /var\(--success\)/ },
  { kind: "var", name: "var(--warning)", pattern: /var\(--warning\)/ },
  { kind: "var", name: "var(--running)", pattern: /var\(--running\)/ },
];

function readSource(relativePath: string): string {
  return readFileSync(resolve(SRC_DIR, relativePath), "utf-8");
}

function collectTokenSweepFindings(
  filePath: string,
  source: string,
  detectors = TOKEN_DETECTORS,
): string[] {
  return detectors.flatMap((detector) =>
    detector.pattern.test(source)
      ? [`${filePath}: retired ${detector.kind} token ${detector.name}`]
      : [],
  );
}

describe("Governance: screen token sweep ownership boundary", () => {
  it("keeps retired files out and protected live files in the sweep", () => {
    for (const filePath of RETIRED_FILES) {
      expect(ALL_FILES).not.toContain(filePath);
    }

    for (const filePath of PROTECTED_LIVE_FILES) {
      expect(ALL_FILES).toContain(filePath);
    }
  });

  it("keeps tracked screen files readable", () => {
    for (const filePath of ALL_FILES) {
      expect(readSource(filePath).length, `${filePath} is empty`).toBeGreaterThan(0);
    }
  });
});

describe("Governance: retired token detector contract", () => {
  it.each(TOKEN_DETECTORS)(
    "detects retired $kind token $name and ignores declared safe variants",
    (detector) => {
      expect(detector.pattern.test(detector.name)).toBe(true);

      for (const safeSample of detector.safeSamples ?? []) {
        expect(detector.pattern.test(safeSample), safeSample).toBe(false);
      }
    },
  );
});

describe("Governance: shipped screen files use product design tokens", () => {
  it.each(FILE_GROUPS)("$name contains no retired screen token references", (group) => {
    const findings = group.files.flatMap((filePath) =>
      collectTokenSweepFindings(filePath, readSource(filePath)),
    );

    expect(findings).toEqual([]);
  });
});
