import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  pageHeaderProps: [] as Array<Record<string, unknown>>,
  dataTableProps: [] as Array<Record<string, unknown>>,
  buttonProps: [] as Array<Record<string, unknown>>,
  soulsQuery: {
    data: [
      {
        id: "soul_alpha",
        role: "Researcher",
        model_name: "gpt-4o",
        provider: "openai",
        avatar_color: "info",
        tools: ["runsight/http"],
        workflow_count: 10,
      },
      {
        id: "soul_beta",
        role: "Analyst",
        model_name: "claude-3-5-sonnet",
        provider: "anthropic",
        avatar_color: "success",
        tools: ["runsight/file-io"],
        workflow_count: 2,
      },
    ],
    isLoading: false,
    isError: false,
  } as {
    data: Array<Record<string, unknown>>;
    isLoading: boolean;
    isError: boolean;
  },
}));

vi.mock("react-router", () => ({
  useNavigate: () => mocks.navigate,
}));

vi.mock("@/queries/souls", () => ({
  useSouls: () => mocks.soulsQuery,
}));

vi.mock("@/components/shared/PageHeader", () => ({
  PageHeader: (props: Record<string, unknown>) => {
    mocks.pageHeaderProps.push(props);
    return React.createElement("page-header", null, props.actions, props.children);
  },
}));

vi.mock("@/components/shared/DataTable", () => ({
  DataTable: (props: Record<string, unknown>) => {
    mocks.dataTableProps.push(props);
    return React.createElement("data-table", null);
  },
}));

vi.mock("@runsight/ui/button", () => ({
  Button: (props: Record<string, unknown>) => {
    mocks.buttonProps.push(props);
    return React.createElement("button", { type: "button", ...props }, props.children);
  },
}));

function resetMocks() {
  mocks.navigate.mockReset();
  mocks.pageHeaderProps.length = 0;
  mocks.dataTableProps.length = 0;
  mocks.buttonProps.length = 0;
}

beforeEach(() => {
  resetMocks();
});

describe("RUN-452 SoulLibraryPage behavior", () => {
  it("builds the page from PageHeader and DataTable directly, with color and tools visible in the current-contract columns", async () => {
    const { Component: SoulLibraryPage } = await import("../SoulLibraryPage");

    renderToStaticMarkup(
      React.createElement(SoulLibraryPage as React.ComponentType<Record<string, unknown>>),
    );

    expect(mocks.pageHeaderProps).toHaveLength(1);
    expect(mocks.dataTableProps).toHaveLength(1);

    const tableProps = mocks.dataTableProps[0] as {
      columns: Array<{ key: string; header: string; sortable?: boolean }>;
      data: Array<Record<string, unknown>>;
      onRowClick?: (row: Record<string, unknown>) => void;
    };

    expect(tableProps.columns.map((column) => column.header)).toEqual(
      expect.arrayContaining(["Name", "Model", "Provider", "Tools", "Used In"]),
    );
    expect(tableProps.columns.some((column) => /Last Modified/i.test(column.header))).toBe(false);
    expect(tableProps.columns.some((column) => column.header === "Used In")).toBe(true);
    expect(tableProps.data).toEqual(mocks.soulsQuery.data);
    expect(String(tableProps.columns.find((column) => column.header === "Name")?.render)).toMatch(
      /avatar_color|bg-|charAt|toUpperCase|text-on-accent/,
    );
    expect(String(tableProps.columns.find((column) => column.header === "Tools")?.render)).toMatch(
      /TOOL_META|HTTP|Files|Icon/,
    );
  });

  it("navigates to /souls/new from the create action and /souls/:id/edit from row selection", async () => {
    const { Component: SoulLibraryPage } = await import("../SoulLibraryPage");

    renderToStaticMarkup(
      React.createElement(SoulLibraryPage as React.ComponentType<Record<string, unknown>>),
    );

    const createButton = mocks.buttonProps.find(
      (props) => typeof props.onClick === "function",
    ) as { onClick?: () => void } | undefined;

    expect(createButton).toBeDefined();
    createButton?.onClick?.();
    expect(mocks.navigate).toHaveBeenCalledWith("/souls/new");

    const tableProps = mocks.dataTableProps[0] as {
      onRowClick?: (row: Record<string, unknown>) => void;
      data: Array<Record<string, unknown>>;
    };

    expect(tableProps.onRowClick).toBeTypeOf("function");
    tableProps.onRowClick?.(tableProps.data[0]);
    expect(mocks.navigate).toHaveBeenCalledWith("/souls/soul_alpha/edit");
  });
});
