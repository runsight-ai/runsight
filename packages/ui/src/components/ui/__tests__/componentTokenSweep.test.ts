/**
 * Component token reference sweep coverage.
 *
 * Governance: source-text boundary coverage for the packages/ui shadcn token
 * migration; this intentionally catches legacy token strings before they ship.
 * Owner: packages/ui design-system maintainers.
 * Boundary: reusable UI primitives under packages/ui/src/components/ui only.
 * Exit criteria: remove this sweep once package-level component tests or lint
 * rules enforce the Runsight token contract directly.
 *
 * Token mapping (old -> new):
 *   bg-background        -> bg-surface-primary
 *   bg-card              -> bg-surface-secondary
 *   bg-popover           -> bg-surface-overlay
 *   bg-primary           -> bg-interactive
 *   bg-secondary         -> bg-surface-tertiary
 *   bg-muted             -> bg-surface-tertiary
 *   bg-accent            -> bg-surface-hover
 *   bg-destructive       -> bg-danger
 *   text-foreground      -> text-primary or text-heading
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
 *   var(--background)    -> var(--surface-primary)
 *   var(--foreground)    -> var(--text-primary)
 *   var(--primary)       -> var(--interactive-default)
 *   var(--border)        -> var(--border-default)
 *   var(--card)          -> var(--surface-secondary)
 *   var(--muted)         -> var(--surface-tertiary)
 *   var(--ring)          -> var(--border-focus)
 *   var(--destructive)   -> var(--danger-9)
 *   var(--input)         -> var(--border-default)
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const UI_DIR = resolve(__dirname, "..");

type OldTokenDetector = {
  name: string;
  kind: "tailwind" | "var";
  pattern: RegExp;
  oldExample: string;
  allowedExamples?: string[];
};

type ComponentTokenCase = {
  filename: string;
  requiresNewToken: boolean;
};

const COMPONENT_TOKEN_CASES: ComponentTokenCase[] = [
  { filename: "badge.tsx", requiresNewToken: true },
  { filename: "button.tsx", requiresNewToken: true },
  { filename: "card.tsx", requiresNewToken: true },
  { filename: "command.tsx", requiresNewToken: true },
  { filename: "dialog.tsx", requiresNewToken: true },
  { filename: "dropdown-menu.tsx", requiresNewToken: true },
  { filename: "input.tsx", requiresNewToken: true },
  { filename: "label.tsx", requiresNewToken: false },
  { filename: "popover.tsx", requiresNewToken: true },
  { filename: "select.tsx", requiresNewToken: true },
  { filename: "sheet.tsx", requiresNewToken: true },
  { filename: "switch.tsx", requiresNewToken: true },
  { filename: "table.tsx", requiresNewToken: true },
  { filename: "tabs.tsx", requiresNewToken: true },
  { filename: "textarea.tsx", requiresNewToken: true },
  { filename: "tooltip.tsx", requiresNewToken: false },
];

const OLD_TOKEN_DETECTORS: OldTokenDetector[] = [
  {
    name: "bg-background",
    kind: "tailwind",
    pattern: /\bbg-background\b/g,
    oldExample: "bg-background",
  },
  {
    name: "bg-card",
    kind: "tailwind",
    pattern: /\bbg-card\b/g,
    oldExample: "bg-card",
  },
  {
    name: "bg-popover",
    kind: "tailwind",
    pattern: /\bbg-popover\b/g,
    oldExample: "bg-popover",
  },
  {
    name: "bg-primary",
    kind: "tailwind",
    pattern: /\bbg-primary(?!-foreground\b)(?![\w-])/g,
    oldExample: "bg-primary",
    allowedExamples: ["bg-primary-foreground"],
  },
  {
    name: "bg-secondary",
    kind: "tailwind",
    pattern: /\bbg-secondary(?!-foreground\b)(?![\w-])/g,
    oldExample: "bg-secondary",
    allowedExamples: ["bg-secondary-foreground"],
  },
  {
    name: "bg-muted",
    kind: "tailwind",
    pattern: /\bbg-muted(?!-foreground\b)(?![\w-])/g,
    oldExample: "bg-muted",
    allowedExamples: ["bg-muted-foreground"],
  },
  {
    name: "bg-accent",
    kind: "tailwind",
    pattern: /\bbg-accent(?!-foreground\b)(?![\w-])/g,
    oldExample: "bg-accent",
    allowedExamples: ["bg-accent-foreground"],
  },
  {
    name: "bg-destructive",
    kind: "tailwind",
    pattern: /\bbg-destructive(?![\w-])/g,
    oldExample: "bg-destructive",
  },
  {
    name: "text-foreground",
    kind: "tailwind",
    pattern: /\btext-foreground(?![\w-])/g,
    oldExample: "text-foreground",
  },
  {
    name: "text-primary-foreground",
    kind: "tailwind",
    pattern: /\btext-primary-foreground\b/g,
    oldExample: "text-primary-foreground",
  },
  {
    name: "text-muted-foreground",
    kind: "tailwind",
    pattern: /\btext-muted-foreground\b/g,
    oldExample: "text-muted-foreground",
  },
  {
    name: "text-card-foreground",
    kind: "tailwind",
    pattern: /\btext-card-foreground\b/g,
    oldExample: "text-card-foreground",
  },
  {
    name: "text-popover-foreground",
    kind: "tailwind",
    pattern: /\btext-popover-foreground\b/g,
    oldExample: "text-popover-foreground",
  },
  {
    name: "text-secondary-foreground",
    kind: "tailwind",
    pattern: /\btext-secondary-foreground\b/g,
    oldExample: "text-secondary-foreground",
  },
  {
    name: "text-accent-foreground",
    kind: "tailwind",
    pattern: /\btext-accent-foreground\b/g,
    oldExample: "text-accent-foreground",
  },
  {
    name: "text-destructive",
    kind: "tailwind",
    pattern: /\btext-destructive(?![\w-])/g,
    oldExample: "text-destructive",
  },
  {
    name: "border-border",
    kind: "tailwind",
    pattern:
      /\bborder-border(?!-default\b)(?!-focus\b)(?!-hover\b)(?!-accent\b)(?!-danger\b)(?!-success\b)(?!-warning\b)(?!-info\b)(?!-subtle\b)(?![\w-])/g,
    oldExample: "border-border",
    allowedExamples: [
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
  {
    name: "border-input",
    kind: "tailwind",
    pattern: /\bborder-input(?![\w-])/g,
    oldExample: "border-input",
  },
  {
    name: "ring-ring",
    kind: "tailwind",
    pattern: /\bring-ring(?![\w-])/g,
    oldExample: "ring-ring",
    allowedExamples: ["ring-border-focus"],
  },
  {
    name: "var(--background)",
    kind: "var",
    pattern: /var\(--background\)/g,
    oldExample: "var(--background)",
  },
  {
    name: "var(--foreground)",
    kind: "var",
    pattern: /var\(--foreground\)/g,
    oldExample: "var(--foreground)",
  },
  {
    name: "var(--primary)",
    kind: "var",
    pattern: /var\(--primary\)/g,
    oldExample: "var(--primary)",
    allowedExamples: ["var(--primary-foreground)"],
  },
  {
    name: "var(--border)",
    kind: "var",
    pattern: /var\(--border\)/g,
    oldExample: "var(--border)",
    allowedExamples: ["var(--border-default)", "var(--border-focus)"],
  },
  {
    name: "var(--card)",
    kind: "var",
    pattern: /var\(--card\)/g,
    oldExample: "var(--card)",
  },
  {
    name: "var(--muted)",
    kind: "var",
    pattern: /var\(--muted\)/g,
    oldExample: "var(--muted)",
    allowedExamples: ["var(--muted-foreground)"],
  },
  {
    name: "var(--ring)",
    kind: "var",
    pattern: /var\(--ring\)/g,
    oldExample: "var(--ring)",
  },
  {
    name: "var(--destructive)",
    kind: "var",
    pattern: /var\(--destructive\)/g,
    oldExample: "var(--destructive)",
  },
  {
    name: "var(--input)",
    kind: "var",
    pattern: /var\(--input\)/g,
    oldExample: "var(--input)",
  },
];

const NEW_TOKEN_PATTERNS = [
  /\bbg-surface-/,
  /\bbg-interactive\b/,
  /\bbg-danger\b/,
  /\bbg-surface-hover\b/,
  /\btext-on-accent\b/,
  /\btext-muted(?!-foreground)(?![\w-])/,
  /\btext-danger\b/,
  /\btext-heading\b/,
  /\bborder-border-default\b/,
  /\bring-border-focus\b/,
  /var\(--surface-primary\)/,
  /var\(--surface-secondary\)/,
  /var\(--surface-tertiary\)/,
  /var\(--surface-overlay\)/,
  /var\(--text-primary\)/,
  /var\(--interactive-default\)/,
  /var\(--border-default\)/,
  /var\(--border-focus\)/,
  /var\(--danger-9\)/,
];

function readComponent(filename: string): string {
  return readFileSync(resolve(UI_DIR, filename), "utf-8");
}

function findOldTokens(source: string, kind?: OldTokenDetector["kind"]): string[] {
  return OLD_TOKEN_DETECTORS.filter(
    (detector) => {
      detector.pattern.lastIndex = 0;
      return (!kind || detector.kind === kind) && detector.pattern.test(source);
    },
  ).map((detector) => detector.name);
}

function hasNewTokens(source: string): boolean {
  return NEW_TOKEN_PATTERNS.some((pattern) => pattern.test(source));
}

describe("component token sweep boundary", () => {
  it.each(COMPONENT_TOKEN_CASES)("$filename exists and is non-empty", ({ filename }) => {
    expect(readComponent(filename).length).toBeGreaterThan(0);
  });

  it.each(COMPONENT_TOKEN_CASES)(
    "$filename contains no old shadcn Tailwind class tokens",
    ({ filename }) => {
      expect(findOldTokens(readComponent(filename), "tailwind")).toEqual([]);
    },
  );

  it.each(COMPONENT_TOKEN_CASES)(
    "$filename contains no old CSS var() token references",
    ({ filename }) => {
      expect(findOldTokens(readComponent(filename), "var")).toEqual([]);
    },
  );

  it.each(COMPONENT_TOKEN_CASES.filter((component) => component.requiresNewToken))(
    "$filename contains at least one new design system token",
    ({ filename }) => {
      expect(hasNewTokens(readComponent(filename))).toBe(true);
    },
  );
});

describe("old token detector contract", () => {
  it.each(OLD_TOKEN_DETECTORS)("$name detects its legacy token", ({ pattern, oldExample }) => {
    pattern.lastIndex = 0;
    expect(pattern.test(oldExample)).toBe(true);
  });

  it.each(OLD_TOKEN_DETECTORS.flatMap((detector) =>
    (detector.allowedExamples ?? []).map((allowedExample) => ({
      ...detector,
      allowedExample,
    })),
  ))(
    "$name does not match allowed adjacent token $allowedExample",
    ({ pattern, allowedExample }) => {
      pattern.lastIndex = 0;
      expect(pattern.test(allowedExample)).toBe(false);
    },
  );

  it.each(OLD_TOKEN_DETECTORS)("$name is absent from every component", ({ name, pattern }) => {
    const offenders = COMPONENT_TOKEN_CASES.flatMap(({ filename }) => {
      pattern.lastIndex = 0;
      return pattern.test(readComponent(filename)) ? [`${filename}: ${name}`] : [];
    });

    expect(offenders).toEqual([]);
  });
});

describe("CVA variant token names", () => {
  it("badge.tsx exports semantic badge variants", () => {
    const source = readComponent("badge.tsx");

    expect(source).toMatch(/export.*badgeVariants/);
    expect(source).toMatch(/variant:\s*\{/);
    expect(source).toMatch(/\baccent\b/);
    expect(source).toMatch(/\bsuccess\b/);
    expect(source).toMatch(/\bwarning\b/);
    expect(source).toMatch(/\bdanger\b/);
    expect(source).toMatch(/\binfo\b/);
    expect(source).toMatch(/\bneutral\b/);
    expect(source).toMatch(/\boutline\b/);
  });

  it("button.tsx exports design-system button variants", () => {
    const source = readComponent("button.tsx");

    expect(source).toMatch(/export.*buttonVariants/);
    expect(source).toMatch(/variant:\s*\{/);
    expect(source).toMatch(/\bprimary\b/);
    expect(source).toMatch(/\bsecondary\b/);
    expect(source).toMatch(/\bghost\b/);
    expect(source).toMatch(/\bdanger\b/);
    expect(source).toMatch(/["']icon-only["']/);
  });
});
