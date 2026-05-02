/**
 * Governance: packages/ui navigation contracts stay with this owner suite.
 * Owner: packages/ui Tabs, Breadcrumb, and Pagination contracts.
 * Boundary: source-text checks for component files, exports, tokens, separator
 * affordances, and range display support under src/components/ui only.
 * Exit criteria: keep one table per contract row and promote new shared
 * navigation coverage here.
 */

import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const UI_DIR = resolve(__dirname, "..");

type ContractRow = {
  component: "Tabs" | "Breadcrumb" | "Pagination";
  filename: string;
  behavior: string;
  pattern: RegExp;
  requiresFile?: boolean;
};

export const NAVIGATION_CONTRACTS: ContractRow[] = [
  {
    component: "Tabs",
    filename: "tabs.tsx",
    behavior: "list border uses the subtle border token",
    pattern: /border-subtle/,
  },
  {
    component: "Tabs",
    filename: "tabs.tsx",
    behavior: "inactive tab text uses the secondary text token",
    pattern: /text-secondary/,
  },
  {
    component: "Tabs",
    filename: "tabs.tsx",
    behavior: "active tab text uses the heading text token",
    pattern: /text-heading/,
  },
  {
    component: "Tabs",
    filename: "tabs.tsx",
    behavior: "active underline uses the default interactive token",
    pattern: /interactive-default/,
  },
  {
    component: "Tabs",
    filename: "tabs.tsx",
    behavior: "tab size uses the small font token",
    pattern: /font-size-sm|text-sm/,
  },
  {
    component: "Tabs",
    filename: "tabs.tsx",
    behavior: "tab weight uses the medium font token",
    pattern: /font-medium|font-weight-medium/,
  },
  {
    component: "Tabs",
    filename: "tabs.tsx",
    behavior: "tab height uses a navigation density token or vertical padding",
    pattern: /density-nav-item-height|h-8|py-2/,
  },
  {
    component: "Breadcrumb",
    filename: "breadcrumb.tsx",
    behavior: "component file exists",
    pattern: /./,
    requiresFile: true,
  },
  {
    component: "Breadcrumb",
    filename: "breadcrumb.tsx",
    behavior: "exports Breadcrumb",
    pattern: /export.*\bBreadcrumb\b/,
  },
  {
    component: "Breadcrumb",
    filename: "breadcrumb.tsx",
    behavior: "exports an item, link, or current page component",
    pattern:
      /export.*\bBreadcrumbItem\b|export.*\bBreadcrumbLink\b|export.*\bBreadcrumbPage\b/,
  },
  {
    component: "Breadcrumb",
    filename: "breadcrumb.tsx",
    behavior: "separator color uses the muted text token",
    pattern: /text-muted/,
  },
  {
    component: "Breadcrumb",
    filename: "breadcrumb.tsx",
    behavior: "current item uses the heading text token",
    pattern: /text-heading/,
  },
  {
    component: "Breadcrumb",
    filename: "breadcrumb.tsx",
    behavior: "ancestor items use secondary or muted text",
    pattern: /text-secondary|text-muted/,
  },
  {
    component: "Breadcrumb",
    filename: "breadcrumb.tsx",
    behavior: "item hover uses the primary text token",
    pattern: /text-primary/,
  },
  {
    component: "Breadcrumb",
    filename: "breadcrumb.tsx",
    behavior: "font size uses the small font token",
    pattern: /font-size-sm|text-sm/,
  },
  {
    component: "Breadcrumb",
    filename: "breadcrumb.tsx",
    behavior: "renders a separator between items",
    pattern: /separator|Separator|chevron|Chevron|slash|\/>/i,
  },
  {
    component: "Pagination",
    filename: "pagination.tsx",
    behavior: "component file exists",
    pattern: /./,
    requiresFile: true,
  },
  {
    component: "Pagination",
    filename: "pagination.tsx",
    behavior: "exports Pagination",
    pattern: /export.*\bPagination\b/,
  },
  {
    component: "Pagination",
    filename: "pagination.tsx",
    behavior: "active page background uses an interactive or selected token",
    pattern: /interactive-default|surface-selected/,
  },
  {
    component: "Pagination",
    filename: "pagination.tsx",
    behavior: "range display text uses secondary or muted text",
    pattern: /text-secondary|text-muted/,
  },
  {
    component: "Pagination",
    filename: "pagination.tsx",
    behavior: "page number buttons use a transparent or ghost style",
    pattern: /ghost|variant.*ghost|Ghost|bg-transparent/,
  },
  {
    component: "Pagination",
    filename: "pagination.tsx",
    behavior: "supports a range display with total count context",
    pattern: /\bof\b|total|count/i,
  },
];

function componentPath(filename: string): string {
  return resolve(UI_DIR, filename);
}

function readComponent(filename: string): string {
  return readFileSync(componentPath(filename), "utf-8");
}

describe("navigation component contracts", () => {
  it.each(NAVIGATION_CONTRACTS)(
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
