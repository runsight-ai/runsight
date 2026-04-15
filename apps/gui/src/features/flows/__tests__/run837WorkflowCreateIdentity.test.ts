// @vitest-environment jsdom

import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { parse } from "yaml";

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  createWorkflow: vi.fn(),
  workflowPayloads: [] as Array<Record<string, unknown>>,
  dateNow: vi.spyOn(Date, "now"),
  mathRandom: vi.spyOn(Math, "random"),
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

describe("RUN-837 FlowsPage workflow create identity", () => {
  beforeEach(() => {
    mocks.navigate.mockReset();
    mocks.createWorkflow.mockReset();
    mocks.workflowPayloads.length = 0;

    mocks.dateNow
      .mockReset()
      .mockReturnValueOnce(1730000000000)
      .mockReturnValueOnce(1730000001000);
    mocks.mathRandom
      .mockReset()
      .mockReturnValueOnce(0.123456789)
      .mockReturnValueOnce(0.987654321);

    mocks.createWorkflow.mockImplementation(
      (
        payload: { yaml?: string },
        options?: { onSuccess?: (workflow: { id: string }) => void },
      ) => {
        mocks.workflowPayloads.push(payload as Record<string, unknown>);
        options?.onSuccess?.({ id: `wf_${mocks.workflowPayloads.length}` });
      },
    );
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("creates two distinct embedded-id payloads when New Workflow is clicked twice", async () => {
    const user = userEvent.setup();

    render(React.createElement(FlowsPage));

    const createButton = screen.getByRole("button", { name: "New Workflow" });

    await user.click(createButton);
    await user.click(createButton);

    expect(mocks.createWorkflow).toHaveBeenCalledTimes(2);
    expect(mocks.workflowPayloads).toHaveLength(2);

    const firstPayload = mocks.workflowPayloads[0];
    const secondPayload = mocks.workflowPayloads[1];
    const firstYaml = parse(String(firstPayload.yaml)) as Record<string, unknown>;
    const secondYaml = parse(String(secondPayload.yaml)) as Record<string, unknown>;

    expect(firstYaml.id).toBeTruthy();
    expect(secondYaml.id).toBeTruthy();
    expect(firstYaml.id).not.toEqual(secondYaml.id);
    expect(firstYaml.id).not.toBe("untitled-workflow");
    expect(secondYaml.id).not.toBe("untitled-workflow");
    expect(String(firstPayload.yaml)).toContain(String(firstYaml.id));
    expect(String(secondPayload.yaml)).toContain(String(secondYaml.id));
    expect(firstYaml.kind).toBe("workflow");
    expect(secondYaml.kind).toBe("workflow");
    expect(mocks.navigate).toHaveBeenNthCalledWith(1, "/workflows/wf_1/edit");
    expect(mocks.navigate).toHaveBeenNthCalledWith(2, "/workflows/wf_2/edit");
  });
});
