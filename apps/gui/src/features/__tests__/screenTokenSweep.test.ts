/**
 * RED-TEAM tests for RUN-296: Screen Token Reference Sweep.
 *
 * Validates that the shipped non-UI-component files in apps/gui/src/ have been
 * updated to use the Runsight Product Design System token names. Tests read
 * each file as a string and assert:
 *   1. No OLD shadcn token class names or var() references remain
 *   2. No OLD extended var() references remain (screen-specific tokens)
 *
 * Scope: pages, layouts, shared components, canvas nodes, utilities.
 * Excludes: components/ui/ (done in RUN-295), __tests__/ dirs.
 *
 * Expected failures (current state):
 *   - Some shipped files still reference old shadcn/custom token names
 *
 * Standard Tailwind class mapping (same as RUN-295):
 *   bg-background        -> bg-surface-primary
 *   bg-card              -> bg-surface-secondary
 *   bg-popover           -> bg-surface-overlay
 *   bg-primary           -> bg-interactive
 *   bg-secondary         -> bg-surface-tertiary
 *   bg-muted             -> bg-surface-tertiary
 *   bg-accent            -> bg-surface-hover
 *   bg-destructive       -> bg-danger
 *   text-foreground      -> text-primary
 *   text-primary-foreground -> text-on-accent
 *   text-muted-foreground   -> text-muted
 *   text-card-foreground    -> text-primary
 *   text-popover-foreground -> text-primary
 *   text-secondary-foreground -> text-primary
 *   text-accent-foreground  -> text-primary
 *   text-destructive     -> text-danger
 *   border-border        -> border-border-default
 *   border-input         -> border-border-default
 *   ring-ring            -> ring-border-focus
 *
 * Extended var() mapping (additional tokens used in screen files):
 *   var(--background)      -> var(--surface-primary)
 *   var(--foreground)      -> var(--text-primary)
 *   var(--primary)         -> var(--interactive-default)  [exact]
 *   var(--primary-hover)   -> var(--interactive-hover)
 *   var(--primary-05)      -> var(--accent-1)
 *   var(--primary-08)      -> var(--accent-2)
 *   var(--primary-10)      -> var(--accent-2)
 *   var(--primary-12)      -> var(--accent-3)
 *   var(--border)          -> var(--border-default)       [exact]
 *   var(--card)            -> var(--surface-secondary)
 *   var(--muted)           -> var(--surface-tertiary)     [exact]
 *   var(--muted-subtle)    -> var(--text-muted)
 *   var(--ring)            -> var(--border-focus)
 *   var(--destructive)     -> var(--danger-9)
 *   var(--input)           -> var(--border-default)
 *   var(--surface)         -> var(--surface-primary)      [exact]
 *   var(--surface-elevated)-> var(--surface-raised)
 *   var(--error)           -> var(--danger-9)             [exact]
 *   var(--error-hover)     -> var(--danger-10)
 *   var(--success)         -> var(--success-9)
 *   var(--warning)         -> var(--warning-9)
 *   var(--running)         -> var(--info-9)
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// ---------------------------------------------------------------------------
// Root directories
// ---------------------------------------------------------------------------

const SRC_DIR = resolve(__dirname, "../..");

function readFile(relativePath: string): string {
  return readFileSync(resolve(SRC_DIR, relativePath), "utf-8");
}

// ---------------------------------------------------------------------------
// Old Tailwind class token detector (identical patterns to RUN-295)
// ---------------------------------------------------------------------------

/**
 * Returns all old Tailwind token class names found in the source string.
 *
 * Negative lookaheads prevent false positives, e.g.:
 *   - `bg-primary` must NOT match `bg-primary-foreground`
 *   - `border-border` must NOT match `border-border-default`
 */
function findOldTailwindTokens(source: string): string[] {
  const patterns: Array<[string, RegExp]> = [
    // bg- tokens — old shadcn utility classes
    ["bg-background", /\bbg-background\b/g],
    ["bg-card", /\bbg-card\b/g],
    ["bg-popover", /\bbg-popover\b/g],
    // bg-primary must NOT match bg-primary-foreground
    ["bg-primary", /\bbg-primary(?!-foreground\b)(?![\w-])/g],
    // bg-secondary must NOT match bg-secondary-foreground
    ["bg-secondary", /\bbg-secondary(?!-foreground\b)(?![\w-])/g],
    // bg-muted standalone (not bg-muted-foreground)
    ["bg-muted", /\bbg-muted(?!-foreground\b)(?![\w-])/g],
    // bg-accent must NOT match bg-accent-foreground
    ["bg-accent", /\bbg-accent(?!-foreground\b)(?![\w-])/g],
    // bg-destructive standalone
    ["bg-destructive", /\bbg-destructive(?![\w-])/g],

    // text- tokens — old shadcn utility classes
    ["text-foreground", /\btext-foreground(?![\w-])/g],
    ["text-primary-foreground", /\btext-primary-foreground\b/g],
    ["text-muted-foreground", /\btext-muted-foreground\b/g],
    ["text-card-foreground", /\btext-card-foreground\b/g],
    ["text-popover-foreground", /\btext-popover-foreground\b/g],
    ["text-secondary-foreground", /\btext-secondary-foreground\b/g],
    ["text-accent-foreground", /\btext-accent-foreground\b/g],
    ["text-destructive", /\btext-destructive(?![\w-])/g],

    // border- tokens — old shadcn utility classes
    // border-border must NOT match border-border-default/-focus/-hover/etc. (new DS)
    [
      "border-border",
      /\bborder-border(?!-default\b)(?!-focus\b)(?!-hover\b)(?!-accent\b)(?!-danger\b)(?!-success\b)(?!-warning\b)(?!-info\b)(?!-subtle\b)(?![\w-])/g,
    ],
    ["border-input", /\bborder-input(?![\w-])/g],

    // ring- tokens
    ["ring-ring", /\bring-ring(?![\w-])/g],
  ];

  const found: string[] = [];
  for (const [name, regex] of patterns) {
    if (regex.test(source)) {
      found.push(name);
    }
  }
  return found;
}

// ---------------------------------------------------------------------------
// Old CSS var() reference detector (standard + extended)
// ---------------------------------------------------------------------------

/**
 * Returns all old CSS var() references found in the source string.
 *
 * Standard tokens (same as RUN-295) plus extended screen-specific tokens.
 * All patterns use literal closing paren `\)` to avoid matching longer
 * variant names, e.g.:
 *   var(--primary)   must NOT match var(--primary-hover)
 *   var(--border)    must NOT match var(--border-default)
 *   var(--surface)   must NOT match var(--surface-primary)
 *   var(--muted)     must NOT match var(--muted-subtle)
 *   var(--error)     must NOT match var(--error-hover)
 */
function findOldVarRefs(source: string): string[] {
  const patterns: Array<[string, RegExp]> = [
    // Standard tokens (shared with RUN-295)
    ["var(--background)", /var\(--background\)/g],
    ["var(--foreground)", /var\(--foreground\)/g],
    // var(--primary) exact — NOT var(--primary-hover) or var(--primary-12)
    ["var(--primary)", /var\(--primary\)/g],
    // var(--border) exact — NOT var(--border-default) etc.
    ["var(--border)", /var\(--border\)/g],
    ["var(--card)", /var\(--card\)/g],
    // var(--muted) exact — NOT var(--muted-subtle)
    ["var(--muted)", /var\(--muted\)/g],
    ["var(--ring)", /var\(--ring\)/g],
    ["var(--destructive)", /var\(--destructive\)/g],
    ["var(--input)", /var\(--input\)/g],

    // Extended tokens (screen-specific)
    ["var(--primary-hover)", /var\(--primary-hover\)/g],
    ["var(--primary-05)", /var\(--primary-05\)/g],
    ["var(--primary-08)", /var\(--primary-08\)/g],
    ["var(--primary-10)", /var\(--primary-10\)/g],
    ["var(--primary-12)", /var\(--primary-12\)/g],
    ["var(--muted-subtle)", /var\(--muted-subtle\)/g],
    // var(--surface) exact — NOT var(--surface-primary) or var(--surface-secondary)
    ["var(--surface)", /var\(--surface\)/g],
    ["var(--surface-elevated)", /var\(--surface-elevated\)/g],
    // var(--error) exact — NOT var(--error-hover)
    ["var(--error)", /var\(--error\)/g],
    ["var(--error-hover)", /var\(--error-hover\)/g],
    ["var(--success)", /var\(--success\)/g],
    ["var(--warning)", /var\(--warning\)/g],
    ["var(--running)", /var\(--running\)/g],
  ];

  const found: string[] = [];
  for (const [name, regex] of patterns) {
    if (regex.test(source)) {
      found.push(name);
    }
  }
  return found;
}

// ---------------------------------------------------------------------------
// File paths (relative to src/)
// ---------------------------------------------------------------------------

const SHARED_COMPONENTS = [
  "components/shared/CrudListPage.tsx",
  "components/shared/DataTable.tsx",
  "components/shared/DeleteConfirmDialog.tsx",
  "components/shared/ErrorBoundary.tsx",
  "components/shared/PageHeader.tsx",
  "components/shared/StatusBadge.tsx",
];

const PROVIDER_COMPONENTS = ["components/provider/ProviderSetup.tsx"];

const CANVAS_FEATURES = [
  "features/canvas/WorkflowCanvas.tsx",
  "features/canvas/nodes/SoulNode.tsx",
  "features/canvas/nodes/StartNode.tsx",
  "features/canvas/nodes/TaskNode.tsx",
];

const RUNS_FEATURES = [
  "features/runs/RunBottomPanel.tsx",
  "features/runs/RunCanvasNode.tsx",
  "features/runs/RunDetail.tsx",
  "features/runs/RunDetailHeader.tsx",
  "features/runs/RunInspectorPanel.tsx",
];

const SETTINGS_FEATURES = [
  "features/settings/ModelsTab.tsx",
  "features/settings/ProvidersTab.tsx",
  "features/settings/SettingsPage.tsx",
];

const OTHER_FEATURES = [
  "features/dashboard/DashboardOrOnboarding.tsx",
  "features/health/HealthPage.tsx",
];

const WORKFLOW_FEATURES = [
  "features/workflows/NewWorkflowModal.tsx",
];

const LAYOUTS = ["routes/layouts/ShellLayout.tsx"];

const UTILITIES = ["utils/icons.tsx"];

const ALL_FILES = [
  ...SHARED_COMPONENTS,
  ...PROVIDER_COMPONENTS,
  ...CANVAS_FEATURES,
  ...RUNS_FEATURES,
  ...SETTINGS_FEATURES,
  ...OTHER_FEATURES,
  ...WORKFLOW_FEATURES,
  ...LAYOUTS,
  ...UTILITIES,
];

// ===========================================================================
// 1. Tracked screen files exist and are readable
// ===========================================================================

describe("Screen files exist", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} exists and is non-empty`, () => {
      const source = readFile(filePath);
      expect(source.length).toBeGreaterThan(0);
    });
  }
});

// ===========================================================================
// 2. Shared components — no old Tailwind tokens
// ===========================================================================

describe("No old Tailwind tokens — shared components", () => {
  for (const filePath of SHARED_COMPONENTS) {
    it(`${filePath} contains no old shadcn Tailwind class tokens`, () => {
      const source = readFile(filePath);
      const found = findOldTailwindTokens(source);
      expect(found, `Old tokens found: ${found.join(", ")}`).toEqual([]);
    });
  }
});

// ===========================================================================
// 3. Shared components — no old var() refs
// ===========================================================================

describe("No old var() refs — shared components", () => {
  for (const filePath of SHARED_COMPONENTS) {
    it(`${filePath} contains no old CSS var() token references`, () => {
      const source = readFile(filePath);
      const found = findOldVarRefs(source);
      expect(found, `Old var() refs found: ${found.join(", ")}`).toEqual([]);
    });
  }
});

// ===========================================================================
// 4. Provider — no old tokens
// ===========================================================================

describe("No old Tailwind tokens — provider", () => {
  for (const filePath of PROVIDER_COMPONENTS) {
    it(`${filePath} contains no old shadcn Tailwind class tokens`, () => {
      const source = readFile(filePath);
      const found = findOldTailwindTokens(source);
      expect(found, `Old tokens found: ${found.join(", ")}`).toEqual([]);
    });
  }
});

describe("No old var() refs — provider", () => {
  for (const filePath of PROVIDER_COMPONENTS) {
    it(`${filePath} contains no old CSS var() token references`, () => {
      const source = readFile(filePath);
      const found = findOldVarRefs(source);
      expect(found, `Old var() refs found: ${found.join(", ")}`).toEqual([]);
    });
  }
});

// ===========================================================================
// 5. Sidebar features — no old tokens
// ===========================================================================

describe("No old Tailwind tokens — sidebar", () => {
  for (const filePath of SIDEBAR_FEATURES) {
    it(`${filePath} contains no old shadcn Tailwind class tokens`, () => {
      const source = readFile(filePath);
      const found = findOldTailwindTokens(source);
      expect(found, `Old tokens found: ${found.join(", ")}`).toEqual([]);
    });
  }
});

describe("No old var() refs — sidebar", () => {
  for (const filePath of SIDEBAR_FEATURES) {
    it(`${filePath} contains no old CSS var() token references`, () => {
      const source = readFile(filePath);
      const found = findOldVarRefs(source);
      expect(found, `Old var() refs found: ${found.join(", ")}`).toEqual([]);
    });
  }
});

// ===========================================================================
// 6. Canvas features — no old tokens
// ===========================================================================

describe("No old Tailwind tokens — canvas", () => {
  for (const filePath of CANVAS_FEATURES) {
    it(`${filePath} contains no old shadcn Tailwind class tokens`, () => {
      const source = readFile(filePath);
      const found = findOldTailwindTokens(source);
      expect(found, `Old tokens found: ${found.join(", ")}`).toEqual([]);
    });
  }
});

describe("No old var() refs — canvas", () => {
  for (const filePath of CANVAS_FEATURES) {
    it(`${filePath} contains no old CSS var() token references`, () => {
      const source = readFile(filePath);
      const found = findOldVarRefs(source);
      expect(found, `Old var() refs found: ${found.join(", ")}`).toEqual([]);
    });
  }
});

// ===========================================================================
// 7. Runs features — no old tokens
// ===========================================================================

describe("No old Tailwind tokens — runs", () => {
  for (const filePath of RUNS_FEATURES) {
    it(`${filePath} contains no old shadcn Tailwind class tokens`, () => {
      const source = readFile(filePath);
      const found = findOldTailwindTokens(source);
      expect(found, `Old tokens found: ${found.join(", ")}`).toEqual([]);
    });
  }
});

describe("No old var() refs — runs", () => {
  for (const filePath of RUNS_FEATURES) {
    it(`${filePath} contains no old CSS var() token references`, () => {
      const source = readFile(filePath);
      const found = findOldVarRefs(source);
      expect(found, `Old var() refs found: ${found.join(", ")}`).toEqual([]);
    });
  }
});

// ===========================================================================
// 8. Settings features — no old tokens
// ===========================================================================

describe("No old Tailwind tokens — settings", () => {
  for (const filePath of SETTINGS_FEATURES) {
    it(`${filePath} contains no old shadcn Tailwind class tokens`, () => {
      const source = readFile(filePath);
      const found = findOldTailwindTokens(source);
      expect(found, `Old tokens found: ${found.join(", ")}`).toEqual([]);
    });
  }
});

describe("No old var() refs — settings", () => {
  for (const filePath of SETTINGS_FEATURES) {
    it(`${filePath} contains no old CSS var() token references`, () => {
      const source = readFile(filePath);
      const found = findOldVarRefs(source);
      expect(found, `Old var() refs found: ${found.join(", ")}`).toEqual([]);
    });
  }
});

// ===========================================================================
// 9. Other feature pages — no old tokens
// ===========================================================================

describe("No old Tailwind tokens — other pages", () => {
  for (const filePath of OTHER_FEATURES) {
    it(`${filePath} contains no old shadcn Tailwind class tokens`, () => {
      const source = readFile(filePath);
      const found = findOldTailwindTokens(source);
      expect(found, `Old tokens found: ${found.join(", ")}`).toEqual([]);
    });
  }
});

describe("No old var() refs — other pages", () => {
  for (const filePath of OTHER_FEATURES) {
    it(`${filePath} contains no old CSS var() token references`, () => {
      const source = readFile(filePath);
      const found = findOldVarRefs(source);
      expect(found, `Old var() refs found: ${found.join(", ")}`).toEqual([]);
    });
  }
});

// ===========================================================================
// 10. Workflow features — no old tokens
// ===========================================================================

describe("No old Tailwind tokens — workflows", () => {
  for (const filePath of WORKFLOW_FEATURES) {
    it(`${filePath} contains no old shadcn Tailwind class tokens`, () => {
      const source = readFile(filePath);
      const found = findOldTailwindTokens(source);
      expect(found, `Old tokens found: ${found.join(", ")}`).toEqual([]);
    });
  }
});

describe("No old var() refs — workflows", () => {
  for (const filePath of WORKFLOW_FEATURES) {
    it(`${filePath} contains no old CSS var() token references`, () => {
      const source = readFile(filePath);
      const found = findOldVarRefs(source);
      expect(found, `Old var() refs found: ${found.join(", ")}`).toEqual([]);
    });
  }
});

// ===========================================================================
// 11. Layouts — no old tokens
// ===========================================================================

describe("No old Tailwind tokens — layouts", () => {
  for (const filePath of LAYOUTS) {
    it(`${filePath} contains no old shadcn Tailwind class tokens`, () => {
      const source = readFile(filePath);
      const found = findOldTailwindTokens(source);
      expect(found, `Old tokens found: ${found.join(", ")}`).toEqual([]);
    });
  }
});

describe("No old var() refs — layouts", () => {
  for (const filePath of LAYOUTS) {
    it(`${filePath} contains no old CSS var() token references`, () => {
      const source = readFile(filePath);
      const found = findOldVarRefs(source);
      expect(found, `Old var() refs found: ${found.join(", ")}`).toEqual([]);
    });
  }
});

// ===========================================================================
// 12. Utilities — no old tokens
// ===========================================================================

describe("No old Tailwind tokens — utilities", () => {
  for (const filePath of UTILITIES) {
    it(`${filePath} contains no old shadcn Tailwind class tokens`, () => {
      const source = readFile(filePath);
      const found = findOldTailwindTokens(source);
      expect(found, `Old tokens found: ${found.join(", ")}`).toEqual([]);
    });
  }
});

describe("No old var() refs — utilities", () => {
  for (const filePath of UTILITIES) {
    it(`${filePath} contains no old CSS var() token references`, () => {
      const source = readFile(filePath);
      const found = findOldVarRefs(source);
      expect(found, `Old var() refs found: ${found.join(", ")}`).toEqual([]);
    });
  }
});

// ===========================================================================
// 13. Comprehensive cross-file sweep — each old Tailwind token absent in
//     ALL 37 files (grouped by token for clear failure messages)
// ===========================================================================

describe("Token sweep completeness: bg-background absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no bg-background`, () => {
      expect(readFile(filePath)).not.toMatch(/\bbg-background\b/);
    });
  }
});

describe("Token sweep completeness: bg-card absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no bg-card`, () => {
      expect(readFile(filePath)).not.toMatch(/\bbg-card\b/);
    });
  }
});

describe("Token sweep completeness: bg-popover absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no bg-popover`, () => {
      expect(readFile(filePath)).not.toMatch(/\bbg-popover\b/);
    });
  }
});

describe("Token sweep completeness: bg-primary absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no bg-primary (standalone, not -foreground)`, () => {
      expect(readFile(filePath)).not.toMatch(/\bbg-primary(?!-foreground\b)(?![\w-])/);
    });
  }
});

describe("Token sweep completeness: bg-secondary absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no bg-secondary (standalone, not -foreground)`, () => {
      expect(readFile(filePath)).not.toMatch(/\bbg-secondary(?!-foreground\b)(?![\w-])/);
    });
  }
});

describe("Token sweep completeness: bg-muted absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no bg-muted (standalone)`, () => {
      expect(readFile(filePath)).not.toMatch(/\bbg-muted(?!-foreground\b)(?![\w-])/);
    });
  }
});

describe("Token sweep completeness: bg-accent absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no bg-accent (standalone, not -foreground)`, () => {
      expect(readFile(filePath)).not.toMatch(/\bbg-accent(?!-foreground\b)(?![\w-])/);
    });
  }
});

describe("Token sweep completeness: bg-destructive absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no bg-destructive`, () => {
      expect(readFile(filePath)).not.toMatch(/\bbg-destructive(?![\w-])/);
    });
  }
});

describe("Token sweep completeness: text-foreground absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no text-foreground`, () => {
      expect(readFile(filePath)).not.toMatch(/\btext-foreground(?![\w-])/);
    });
  }
});

describe("Token sweep completeness: text-primary-foreground absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no text-primary-foreground`, () => {
      expect(readFile(filePath)).not.toMatch(/\btext-primary-foreground\b/);
    });
  }
});

describe("Token sweep completeness: text-muted-foreground absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no text-muted-foreground`, () => {
      expect(readFile(filePath)).not.toMatch(/\btext-muted-foreground\b/);
    });
  }
});

describe("Token sweep completeness: text-card-foreground absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no text-card-foreground`, () => {
      expect(readFile(filePath)).not.toMatch(/\btext-card-foreground\b/);
    });
  }
});

describe("Token sweep completeness: text-popover-foreground absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no text-popover-foreground`, () => {
      expect(readFile(filePath)).not.toMatch(/\btext-popover-foreground\b/);
    });
  }
});

describe("Token sweep completeness: text-secondary-foreground absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no text-secondary-foreground`, () => {
      expect(readFile(filePath)).not.toMatch(/\btext-secondary-foreground\b/);
    });
  }
});

describe("Token sweep completeness: text-accent-foreground absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no text-accent-foreground`, () => {
      expect(readFile(filePath)).not.toMatch(/\btext-accent-foreground\b/);
    });
  }
});

describe("Token sweep completeness: text-destructive absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no text-destructive`, () => {
      expect(readFile(filePath)).not.toMatch(/\btext-destructive(?![\w-])/);
    });
  }
});

describe("Token sweep completeness: border-border (old) absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no border-border (old — not border-border-default)`, () => {
      expect(readFile(filePath)).not.toMatch(
        /\bborder-border(?!-default\b)(?!-focus\b)(?!-hover\b)(?!-accent\b)(?!-danger\b)(?!-success\b)(?!-warning\b)(?!-info\b)(?!-subtle\b)(?![\w-])/
      );
    });
  }
});

describe("Token sweep completeness: border-input absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no border-input`, () => {
      expect(readFile(filePath)).not.toMatch(/\bborder-input(?![\w-])/);
    });
  }
});

describe("Token sweep completeness: ring-ring absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no ring-ring`, () => {
      expect(readFile(filePath)).not.toMatch(/\bring-ring(?![\w-])/);
    });
  }
});

// Standard var() tokens
describe("Token sweep completeness: var(--background) absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no var(--background)`, () => {
      expect(readFile(filePath)).not.toMatch(/var\(--background\)/);
    });
  }
});

describe("Token sweep completeness: var(--foreground) absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no var(--foreground)`, () => {
      expect(readFile(filePath)).not.toMatch(/var\(--foreground\)/);
    });
  }
});

describe("Token sweep completeness: var(--primary) absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no var(--primary) (exact)`, () => {
      expect(readFile(filePath)).not.toMatch(/var\(--primary\)/);
    });
  }
});

describe("Token sweep completeness: var(--border) absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no var(--border) (exact)`, () => {
      expect(readFile(filePath)).not.toMatch(/var\(--border\)/);
    });
  }
});

describe("Token sweep completeness: var(--card) absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no var(--card)`, () => {
      expect(readFile(filePath)).not.toMatch(/var\(--card\)/);
    });
  }
});

describe("Token sweep completeness: var(--muted) absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no var(--muted) (exact)`, () => {
      expect(readFile(filePath)).not.toMatch(/var\(--muted\)/);
    });
  }
});

describe("Token sweep completeness: var(--ring) absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no var(--ring)`, () => {
      expect(readFile(filePath)).not.toMatch(/var\(--ring\)/);
    });
  }
});

describe("Token sweep completeness: var(--destructive) absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no var(--destructive)`, () => {
      expect(readFile(filePath)).not.toMatch(/var\(--destructive\)/);
    });
  }
});

describe("Token sweep completeness: var(--input) absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no var(--input)`, () => {
      expect(readFile(filePath)).not.toMatch(/var\(--input\)/);
    });
  }
});

// Extended var() tokens (screen-specific)
describe("Token sweep completeness: var(--primary-hover) absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no var(--primary-hover)`, () => {
      expect(readFile(filePath)).not.toMatch(/var\(--primary-hover\)/);
    });
  }
});

describe("Token sweep completeness: var(--primary-05) absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no var(--primary-05)`, () => {
      expect(readFile(filePath)).not.toMatch(/var\(--primary-05\)/);
    });
  }
});

describe("Token sweep completeness: var(--primary-08) absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no var(--primary-08)`, () => {
      expect(readFile(filePath)).not.toMatch(/var\(--primary-08\)/);
    });
  }
});

describe("Token sweep completeness: var(--primary-10) absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no var(--primary-10)`, () => {
      expect(readFile(filePath)).not.toMatch(/var\(--primary-10\)/);
    });
  }
});

describe("Token sweep completeness: var(--primary-12) absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no var(--primary-12)`, () => {
      expect(readFile(filePath)).not.toMatch(/var\(--primary-12\)/);
    });
  }
});

describe("Token sweep completeness: var(--muted-subtle) absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no var(--muted-subtle)`, () => {
      expect(readFile(filePath)).not.toMatch(/var\(--muted-subtle\)/);
    });
  }
});

describe("Token sweep completeness: var(--surface) absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no var(--surface) (exact)`, () => {
      expect(readFile(filePath)).not.toMatch(/var\(--surface\)/);
    });
  }
});

describe("Token sweep completeness: var(--surface-elevated) absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no var(--surface-elevated)`, () => {
      expect(readFile(filePath)).not.toMatch(/var\(--surface-elevated\)/);
    });
  }
});

describe("Token sweep completeness: var(--error) absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no var(--error) (exact)`, () => {
      expect(readFile(filePath)).not.toMatch(/var\(--error\)/);
    });
  }
});

describe("Token sweep completeness: var(--error-hover) absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no var(--error-hover)`, () => {
      expect(readFile(filePath)).not.toMatch(/var\(--error-hover\)/);
    });
  }
});

describe("Token sweep completeness: var(--success) absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no var(--success)`, () => {
      expect(readFile(filePath)).not.toMatch(/var\(--success\)/);
    });
  }
});

describe("Token sweep completeness: var(--warning) absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no var(--warning)`, () => {
      expect(readFile(filePath)).not.toMatch(/var\(--warning\)/);
    });
  }
});

describe("Token sweep completeness: var(--running) absent in all screen files", () => {
  for (const filePath of ALL_FILES) {
    it(`${filePath} has no var(--running)`, () => {
      expect(readFile(filePath)).not.toMatch(/var\(--running\)/);
    });
  }
});
