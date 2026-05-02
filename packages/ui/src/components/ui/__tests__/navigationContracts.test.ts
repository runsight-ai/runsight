/**
 * Governance: packages/ui navigation contracts stay with this owner suite.
 * Owner: packages/ui Tabs, Breadcrumb, and Pagination contracts.
 * Boundary: public component exports only; rendered navigation behavior belongs
 * to rendered navigation owner suites.
 * Exit criteria: keep this smoke until package exports are validated by a
 * generated manifest or type-contract owner.
 */

import { describe, expect, it } from "vitest";
import {
  Breadcrumb,
  BreadcrumbEllipsis,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "../breadcrumb";
import { Pagination } from "../pagination";
import { TabBadge, Tabs, TabsContent, TabsList, TabsTrigger } from "../tabs";

type ExportSmoke = {
  component: "Tabs" | "Breadcrumb" | "Pagination";
  publicExports: Array<readonly [string, unknown]>;
};

export const NAVIGATION_CONTRACTS: ExportSmoke[] = [
  {
    component: "Tabs",
    publicExports: [
      ["Tabs", Tabs],
      ["TabsList", TabsList],
      ["TabsTrigger", TabsTrigger],
      ["TabsContent", TabsContent],
      ["TabBadge", TabBadge],
    ],
  },
  {
    component: "Breadcrumb",
    publicExports: [
      ["Breadcrumb", Breadcrumb],
      ["BreadcrumbList", BreadcrumbList],
      ["BreadcrumbItem", BreadcrumbItem],
      ["BreadcrumbLink", BreadcrumbLink],
      ["BreadcrumbPage", BreadcrumbPage],
      ["BreadcrumbSeparator", BreadcrumbSeparator],
      ["BreadcrumbEllipsis", BreadcrumbEllipsis],
    ],
  },
  { component: "Pagination", publicExports: [["Pagination", Pagination]] },
];

describe("navigation public contract smoke", () => {
  it.each(NAVIGATION_CONTRACTS)(
    "$component keeps expected public exports defined",
    ({ publicExports }) => {
      for (const [name, value] of publicExports) {
        expect(value, `${name} should remain exported`).toBeDefined();
      }
    },
  );
});
