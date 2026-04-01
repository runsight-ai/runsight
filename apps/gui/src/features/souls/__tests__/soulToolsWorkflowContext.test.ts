// @vitest-environment jsdom

import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SoulToolsSection } from "../SoulToolsSection";

type WorkflowToolContext = {
  id: string;
  label: string;
  description: string;
  enabled: boolean;
};

const WORKFLOW_TOOLS: WorkflowToolContext[] = [
  {
    id: "http_tool",
    label: "HTTP Requests",
    description: "Fetch external APIs.",
    enabled: true,
  },
  {
    id: "file_tool",
    label: "Workspace Files",
    description: "Read project files.",
    enabled: false,
  },
  {
    id: "delegate_tool",
    label: "Delegate",
    description: "Route between exits.",
    enabled: false,
  },
];

const FORM_VALUES = {
  name: "Researcher",
  avatarColor: "accent",
  providerId: null,
  provider: null,
  modelId: null,
  systemPrompt: "Research the topic.",
  tools: ["http_tool"],
  temperature: 0.7,
  maxTokens: null,
  maxToolIterations: 3,
};

describe("RUN-490 workflow tool context rendering", () => {
  it("renders every workflow tool and shows informational state for tools not enabled on the soul", () => {
    render(
      React.createElement(SoulToolsSection as unknown as React.ComponentType<any>, {
        tools: ["http_tool"],
        workflowTools: WORKFLOW_TOOLS,
        onToolsChange: vi.fn(),
      }),
    );

    fireEvent.click(screen.getByRole("button", { name: /tools/i }));

    expect(screen.getByText("HTTP Requests")).toBeTruthy();
    expect(screen.getByText("Workspace Files")).toBeTruthy();
    expect(screen.getByText("Delegate")).toBeTruthy();
    expect(screen.getByText("Enabled")).toBeTruthy();

    const informationalBadges = screen.getAllByText("Available in workflow");
    expect(informationalBadges).toHaveLength(2);
    for (const badge of informationalBadges) {
      expect(badge.className).toMatch(/amber|warning/i);
    }
  });

  it("passes workflow tool context through SoulFormBody into the tools section", async () => {
    vi.resetModules();
    vi.doMock("../SoulIdentitySection", () => ({
      SoulIdentitySection: () => React.createElement("div", null, "identity"),
    }));
    vi.doMock("../SoulModelSection", () => ({
      SoulModelSection: () => React.createElement("div", null, "model"),
    }));
    vi.doMock("../SoulPromptSection", () => ({
      SoulPromptSection: () => React.createElement("div", null, "prompt"),
    }));
    vi.doMock("../SoulAdvancedSection", () => ({
      SoulAdvancedSection: () => React.createElement("div", null, "advanced"),
    }));
    vi.doMock("../SoulToolsSection", () => ({
      SoulToolsSection: (props: { workflowTools?: WorkflowToolContext[] }) =>
        React.createElement(
          "section",
          { "data-testid": "workflow-tools-prop" },
          props.workflowTools?.map((tool) =>
            React.createElement(
              "div",
              { key: tool.id },
              tool.label,
              tool.enabled
                ? React.createElement("span", null, "Enabled")
                : React.createElement(
                    "span",
                    { className: "amber-state" },
                    "Available in workflow",
                  ),
            ),
          ) ?? null,
        ),
    }));

    const { SoulFormBody } = await import("../SoulFormBody");

    render(
      React.createElement(SoulFormBody as unknown as React.ComponentType<any>, {
        values: FORM_VALUES,
        workflowTools: WORKFLOW_TOOLS,
        setField: vi.fn(),
      }),
    );

    expect(screen.getByText("HTTP Requests")).toBeTruthy();
    expect(screen.getByText("Workspace Files")).toBeTruthy();
    expect(screen.getByText("Delegate")).toBeTruthy();
    expect(screen.getAllByText("Available in workflow")).toHaveLength(2);
  });
});
