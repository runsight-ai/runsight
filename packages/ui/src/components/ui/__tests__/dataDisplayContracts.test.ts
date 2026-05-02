/**
 * Governance: packages/ui data display contracts stay with this owner suite.
 * Owner: packages/ui Table, Card, StatCard, and CodeBlock contracts.
 * Boundary: source-text checks for component files, exports, tokens, visual
 * affordances, and copy support under src/components/ui only.
 * Exit criteria: keep one table per contract row and promote new shared data
 * display coverage here.
 */

import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const UI_DIR = resolve(__dirname, "..");

type ContractRow = {
  component: "Table" | "Card" | "StatCard" | "CodeBlock";
  filename: string;
  behavior: string;
  pattern: RegExp;
  requiresFile?: boolean;
};

export const DATA_DISPLAY_CONTRACTS: ContractRow[] = [
  {
    component: "Table",
    filename: "table.tsx",
    behavior: "header background uses a surface token",
    pattern: /surface-secondary|surface-primary/,
  },
  {
    component: "Table",
    filename: "table.tsx",
    behavior: "header cell text uses a secondary or muted token",
    pattern: /text-secondary|text-muted/,
  },
  {
    component: "Table",
    filename: "table.tsx",
    behavior: "header cell size uses an extra small text token",
    pattern: /font-size-xs|text-2xs/,
  },
  {
    component: "Table",
    filename: "table.tsx",
    behavior: "header cells use uppercase labels",
    pattern: /uppercase/,
  },
  {
    component: "Table",
    filename: "table.tsx",
    behavior: "row hover uses the hover surface token",
    pattern: /surface-hover/,
  },
  {
    component: "Table",
    filename: "table.tsx",
    behavior: "borders use the subtle border token",
    pattern: /border-subtle/,
  },
  {
    component: "Table",
    filename: "table.tsx",
    behavior: "row height uses a density token",
    pattern: /density-row-height|density/,
  },
  {
    component: "Table",
    filename: "table.tsx",
    behavior: "monospaced values use the mono font token",
    pattern: /font-mono/,
  },
  {
    component: "Card",
    filename: "card.tsx",
    behavior: "border uses the subtle border token",
    pattern: /border-subtle/,
  },
  {
    component: "Card",
    filename: "card.tsx",
    behavior: "radius uses the large radius token",
    pattern: /radius-lg|rounded-lg/,
  },
  {
    component: "Card",
    filename: "card.tsx",
    behavior: "padding uses the fourth spacing token",
    pattern: /space-4|p-4/,
  },
  {
    component: "Card",
    filename: "card.tsx",
    behavior: "header text uses the heading text token",
    pattern: /text-heading/,
  },
  {
    component: "StatCard",
    filename: "stat-card.tsx",
    behavior: "component file exists",
    pattern: /./,
    requiresFile: true,
  },
  {
    component: "StatCard",
    filename: "stat-card.tsx",
    behavior: "exports StatCard",
    pattern: /export.*\bStatCard\b/,
  },
  {
    component: "StatCard",
    filename: "stat-card.tsx",
    behavior: "label uses a secondary or muted text token",
    pattern: /text-secondary|text-muted/,
  },
  {
    component: "StatCard",
    filename: "stat-card.tsx",
    behavior: "label size uses the extra small font token",
    pattern: /font-size-xs/,
  },
  {
    component: "StatCard",
    filename: "stat-card.tsx",
    behavior: "value display uses the mono font token",
    pattern: /font-mono/,
  },
  {
    component: "StatCard",
    filename: "stat-card.tsx",
    behavior: "value size uses a large display text token",
    pattern: /font-size-2xl|text-2xl|text-3xl/,
  },
  {
    component: "StatCard",
    filename: "stat-card.tsx",
    behavior: "value text uses the heading text token",
    pattern: /text-heading/,
  },
  {
    component: "StatCard",
    filename: "stat-card.tsx",
    behavior: "renders a top category stripe",
    pattern: /stripe|border-t|border-top|inset-x/,
  },
  {
    component: "StatCard",
    filename: "stat-card.tsx",
    behavior: "label uses uppercase text",
    pattern: /uppercase/,
  },
  {
    component: "StatCard",
    filename: "stat-card.tsx",
    behavior: "supports an optional delta indicator",
    pattern: /delta|Delta|change|trend/i,
  },
  {
    component: "CodeBlock",
    filename: "code-block.tsx",
    behavior: "component file exists",
    pattern: /./,
    requiresFile: true,
  },
  {
    component: "CodeBlock",
    filename: "code-block.tsx",
    behavior: "exports CodeBlock",
    pattern: /export.*\bCodeBlock\b/,
  },
  {
    component: "CodeBlock",
    filename: "code-block.tsx",
    behavior: "background uses a neutral or primary surface token",
    pattern: /neutral-2|surface-primary/,
  },
  {
    component: "CodeBlock",
    filename: "code-block.tsx",
    behavior: "font family uses the mono font token",
    pattern: /font-mono/,
  },
  {
    component: "CodeBlock",
    filename: "code-block.tsx",
    behavior: "font size uses the small font token",
    pattern: /font-size-sm|text-sm/,
  },
  {
    component: "CodeBlock",
    filename: "code-block.tsx",
    behavior: "keyword highlighting uses the syntax key token",
    pattern: /syntax-key/,
  },
  {
    component: "CodeBlock",
    filename: "code-block.tsx",
    behavior: "string highlighting uses the syntax string token",
    pattern: /syntax-string/,
  },
  {
    component: "CodeBlock",
    filename: "code-block.tsx",
    behavior: "value highlighting uses the syntax value token",
    pattern: /syntax-value/,
  },
  {
    component: "CodeBlock",
    filename: "code-block.tsx",
    behavior: "renders a copy button",
    pattern: /copy|Copy|clipboard|Clipboard/i,
  },
];

function componentPath(filename: string): string {
  return resolve(UI_DIR, filename);
}

function readComponent(filename: string): string {
  return readFileSync(componentPath(filename), "utf-8");
}

describe("data display component contracts", () => {
  it.each(DATA_DISPLAY_CONTRACTS)(
    "$component $behavior",
    ({ filename, pattern, requiresFile }) => {
      const path = componentPath(filename);

      if (requiresFile) {
        expect(existsSync(path)).toBe(true);
        return;
      }

      expect(readComponent(filename)).toMatch(pattern);
    },
  );
});
