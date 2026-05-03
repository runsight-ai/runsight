// @vitest-environment jsdom

import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  createWorkflow: vi.fn(),
}));

vi.mock("react-router", () => ({
  useNavigate: () => mocks.navigate,
}));

vi.mock("@/queries/workflows", () => ({
  useCreateWorkflow: () => ({
    mutate: mocks.createWorkflow,
    isPending: false,
  }),
}));

vi.mock("@/components/shared", () => ({
  PageHeader: ({
    title,
    actions,
  }: {
    title: string;
    actions?: React.ReactNode;
  }) =>
    React.createElement("header", null, [
      React.createElement("h1", { key: "title" }, title),
      React.createElement("div", { key: "actions" }, actions),
    ]),
}));

vi.mock("@runsight/ui/button", () => ({
  Button: ({
    children,
    onClick,
    disabled,
    type,
    ...props
  }: {
    children?: React.ReactNode;
    onClick?: () => void;
    disabled?: boolean;
    type?: "button" | "submit" | "reset";
  }) =>
    React.createElement(
      "button",
      {
        type: type ?? "button",
        onClick,
        disabled,
        ...props,
      },
      children,
    ),
}));

vi.mock("@runsight/ui/tabs", () => ({
  Tabs: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", { role: "tablist" }, children),
  TabsList: ({ children }: { children: React.ReactNode }) =>
    React.createElement("div", null, children),
  TabsTrigger: ({ children }: { children: React.ReactNode }) =>
    React.createElement("button", { type: "button" }, children),
  TabsContent: ({ children }: { children: React.ReactNode }) =>
    React.createElement("section", null, children),
}));

vi.mock("../WorkflowsTab", () => ({
  WorkflowsTab: () => React.createElement("div", null, "workflows-tab"),
}));

vi.mock("lucide-react", () => ({
  Plus: () => React.createElement("span", { "aria-hidden": "true" }, "+"),
}));

import { Component as FlowsPage } from "../FlowsPage";

describe("FlowsPage workflow create identity", () => {
  beforeEach(() => {
    mocks.navigate.mockReset();
    mocks.createWorkflow.mockReset();

    mocks.createWorkflow.mockImplementation(
      (
        _createRequest: unknown,
        options?: { onSuccess?: (workflow: { id: string }) => void },
      ) => {
        const createdWorkflowIds = ["created_research_flow", "created_review_flow"];
        const createdWorkflowIndex = mocks.createWorkflow.mock.calls.length - 1;
        options?.onSuccess?.({
          id: createdWorkflowIds[createdWorkflowIndex] ?? "created_extra_flow",
        });
      },
    );
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("creates workflows and navigates to each created workflow editor", async () => {
    const user = userEvent.setup();

    render(React.createElement(FlowsPage));

    const createButton = screen.getByRole("button", { name: "New Workflow" });

    await user.click(createButton);
    await user.click(createButton);

    expect(mocks.createWorkflow).toHaveBeenCalledTimes(2);
    expect(mocks.navigate).toHaveBeenNthCalledWith(
      1,
      "/workflows/created_research_flow/edit",
    );
    expect(mocks.navigate).toHaveBeenNthCalledWith(
      2,
      "/workflows/created_review_flow/edit",
    );
  });
});
