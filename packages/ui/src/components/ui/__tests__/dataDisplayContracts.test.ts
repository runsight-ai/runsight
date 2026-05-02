/**
 * Governance: packages/ui data display contracts stay with this owner suite.
 * Owner: packages/ui Table, Card, StatCard, and CodeBlock contracts.
 * Boundary: public component exports only; rendered copy, layout, and visual
 * behavior belongs to rendered display and copy owner suites.
 * Exit criteria: keep this smoke until package exports are validated by a
 * generated manifest or type-contract owner.
 */

import { describe, expect, it } from "vitest";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "../card";
import {
  CodeBlock,
  SyntaxComment,
  SyntaxKey,
  SyntaxPunct,
  SyntaxString,
  SyntaxValue,
} from "../code-block";
import { StatCard } from "../stat-card";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableMonoCell,
  TableRow,
} from "../table";

type ExportSmoke = {
  component: "Table" | "Card" | "StatCard" | "CodeBlock";
  publicExports: Array<readonly [string, unknown]>;
};

export const DATA_DISPLAY_CONTRACTS: ExportSmoke[] = [
  {
    component: "Table",
    publicExports: [
      ["Table", Table],
      ["TableHeader", TableHeader],
      ["TableBody", TableBody],
      ["TableFooter", TableFooter],
      ["TableHead", TableHead],
      ["TableRow", TableRow],
      ["TableCell", TableCell],
      ["TableMonoCell", TableMonoCell],
      ["TableCaption", TableCaption],
    ],
  },
  {
    component: "Card",
    publicExports: [
      ["Card", Card],
      ["CardHeader", CardHeader],
      ["CardFooter", CardFooter],
      ["CardTitle", CardTitle],
      ["CardAction", CardAction],
      ["CardDescription", CardDescription],
      ["CardContent", CardContent],
    ],
  },
  {
    component: "StatCard",
    publicExports: [["StatCard", StatCard]],
  },
  {
    component: "CodeBlock",
    publicExports: [
      ["CodeBlock", CodeBlock],
      ["SyntaxKey", SyntaxKey],
      ["SyntaxString", SyntaxString],
      ["SyntaxValue", SyntaxValue],
      ["SyntaxComment", SyntaxComment],
      ["SyntaxPunct", SyntaxPunct],
    ],
  },
];

describe("data display public contract smoke", () => {
  it.each(DATA_DISPLAY_CONTRACTS)(
    "$component keeps expected public exports defined",
    ({ publicExports }) => {
      for (const [name, value] of publicExports) {
        expect(value, `${name} should remain exported`).toBeDefined();
      }
    },
  );
});
