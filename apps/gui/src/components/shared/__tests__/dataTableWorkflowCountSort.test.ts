import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  stateValues: [] as unknown[],
  stateCursor: 0,
  tableHeadProps: [] as Array<Record<string, unknown>>,
  tableRowProps: [] as Array<Record<string, unknown>>,
}));

vi.mock("react", async () => {
  const actual = await vi.importActual<typeof React>("react");

  return {
    ...actual,
    useState: <T,>(initial: T | (() => T)) => {
      const index = mocks.stateCursor++;

      if (!(index in mocks.stateValues)) {
        mocks.stateValues[index] =
          typeof initial === "function" ? (initial as () => T)() : initial;
      }

      const setState = (value: T | ((previous: T) => T)) => {
        const previous = mocks.stateValues[index] as T;
        mocks.stateValues[index] =
          typeof value === "function"
            ? (value as (previous: T) => T)(previous)
            : value;
      };

      return [mocks.stateValues[index] as T, setState] as const;
    },
    useMemo: <T,>(factory: () => T) => factory(),
  };
});

vi.mock("@/utils/helpers", () => ({
  cn: (...classes: Array<string | undefined | false | null>) =>
    classes.filter(Boolean).join(" "),
}));

vi.mock("@runsight/ui/input", () => ({
  Input: (props: Record<string, unknown>) => React.createElement("input", props),
}));

vi.mock("@runsight/ui/table", () => ({
  Table: ({ children }: { children: React.ReactNode }) =>
    React.createElement("table", null, children),
  TableBody: ({ children }: { children: React.ReactNode }) =>
    React.createElement("tbody", null, children),
  TableCell: ({ children, ...props }: Record<string, unknown>) =>
    React.createElement("td", props, children),
  TableHead: ({ children, ...props }: Record<string, unknown>) => {
    mocks.tableHeadProps.push({ children, ...props });
    return React.createElement("th", props, children);
  },
  TableHeader: ({ children }: { children: React.ReactNode }) =>
    React.createElement("thead", null, children),
  TableRow: ({ children, ...props }: Record<string, unknown>) => {
    mocks.tableRowProps.push({ children, ...props });
    return React.createElement("tr", props, children);
  },
}));

vi.mock("lucide-react", () => ({
  ChevronUp: () => React.createElement("svg", { "data-icon": "ChevronUp" }),
  ChevronDown: () => React.createElement("svg", { "data-icon": "ChevronDown" }),
  Search: () => React.createElement("svg", { "data-icon": "Search" }),
}));

const { DataTable } = await import("../DataTable");

function textContent(node: React.ReactNode): string {
  if (node == null || typeof node === "boolean") {
    return "";
  }

  if (typeof node === "string" || typeof node === "number") {
    return String(node);
  }

  if (!React.isValidElement(node)) {
    return "";
  }

  return React.Children.toArray(node.props.children).map(textContent).join("");
}

function bodyMarkup(markup: string): string {
  const start = markup.indexOf("<tbody");
  const end = markup.indexOf("</tbody>");

  return start >= 0 && end >= 0 ? markup.slice(start, end) : markup;
}

beforeEach(() => {
  mocks.stateValues.length = 0;
  mocks.stateCursor = 0;
  mocks.tableHeadProps.length = 0;
  mocks.tableRowProps.length = 0;
});

describe("RUN-452 Used In numeric ordering", () => {
  it("sorts workflow_count numerically after the Used In header is activated", () => {
    const columns = [
      { key: "role", header: "Name", sortable: true },
      { key: "model_name", header: "Model", sortable: true },
      { key: "workflow_count", header: "Used In", sortable: true },
    ];
    const data = [
      { role: "Beta", workflow_count: 10 },
      { role: "Alpha", workflow_count: 2 },
    ];

    mocks.stateCursor = 0;
    const firstMarkup = renderToStaticMarkup(
      React.createElement(DataTable as React.ComponentType<Record<string, unknown>>, {
      columns,
      data,
      sortable: true,
    }));

    const firstBody = bodyMarkup(firstMarkup);
    expect(firstBody.indexOf(">Beta<")).toBeLessThan(firstBody.indexOf(">Alpha<"));

    const usedInHead = mocks.tableHeadProps.find((props) =>
      textContent(props.children).includes("Used In"),
    ) as { onClick?: () => void } | undefined;

    expect(usedInHead?.onClick).toBeTypeOf("function");
    usedInHead?.onClick?.();

    mocks.stateCursor = 0;
    const secondMarkup = renderToStaticMarkup(
      React.createElement(DataTable as React.ComponentType<Record<string, unknown>>, {
      columns,
      data,
      sortable: true,
    }));

    const secondBody = bodyMarkup(secondMarkup);
    expect(secondBody.indexOf(">Alpha<")).toBeLessThan(secondBody.indexOf(">Beta<"));
  });
});
