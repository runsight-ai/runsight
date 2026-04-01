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
  availableInWorkflow?: boolean;
};

type AvailableTool = {
  slug: string;
  name: string;
  description: string;
  type: "builtin" | "custom" | "http";
};

const WORKFLOW_TOOLS: WorkflowToolContext[] = [
  {
    id: "runsight/http",
    label: "HTTP Requests",
    description: "Fetch external APIs.",
    enabled: true,
  },
  {
    id: "runsight/file-io",
    label: "Workspace Files",
    description: "Read project files.",
    enabled: false,
  },
  {
    id: "report_lookup",
    label: "Report Lookup",
    description: "Look up saved reports.",
    enabled: false,
    availableInWorkflow: false,
  },
  {
    id: "runsight/delegate",
    label: "Delegate",
    description: "Delegate work to sub-agents.",
    enabled: false,
  },
];

const AVAILABLE_TOOLS: AvailableTool[] = [
  {
    slug: "runsight/http",
    name: "HTTP Requests",
    description: "Fetch external APIs.",
    type: "builtin",
  },
  {
    slug: "runsight/file-io",
    name: "Workspace Files",
    description: "Read project files.",
    type: "builtin",
  },
  {
    slug: "report_lookup",
    name: "Report Lookup",
    description: "Look up saved reports.",
    type: "custom",
  },
];

const FORM_VALUES = {
  name: "Researcher",
  avatarColor: "accent",
  providerId: null,
  provider: null,
  modelId: null,
  systemPrompt: "Research the topic.",
  tools: ["runsight/http"],
  temperature: 0.7,
  maxTokens: null,
  maxToolIterations: 3,
};

describe("RUN-490 workflow tool context rendering", () => {
  it("renders every workflow tool and shows informational state for tools not enabled on the soul", () => {
    render(
      React.createElement(SoulToolsSection as unknown as React.ComponentType<any>, {
        tools: ["runsight/http"],
        workflowTools: WORKFLOW_TOOLS,
        availableTools: AVAILABLE_TOOLS,
        onToolsChange: vi.fn(),
      }),
    );

    fireEvent.click(screen.getByRole("button", { name: /tools/i }));

    const httpToolButton = screen.getByRole("button", { name: /http requests/i });

    expect(httpToolButton).toBeTruthy();
    expect(httpToolButton.getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByText("Workspace Files")).toBeTruthy();
    expect(screen.getByText("Report Lookup")).toBeTruthy();
    expect(screen.queryByText("Delegate")).toBeNull();
    const customBadge = screen.getByText("Custom");
    expect(customBadge.className).toMatch(/amber|warning/i);
    const workflowBadge = screen.getByText("Not enabled in workflow");
    expect(workflowBadge.className).toMatch(/amber|warning/i);
  });

  it("toggles API-discovered tool slugs when the user enables a tool", () => {
    const onToolsChange = vi.fn();

    render(
      React.createElement(SoulToolsSection as unknown as React.ComponentType<any>, {
        tools: ["runsight/http"],
        workflowTools: WORKFLOW_TOOLS,
        availableTools: AVAILABLE_TOOLS,
        onToolsChange,
      }),
    );

    fireEvent.click(screen.getByRole("button", { name: /tools/i }));
    fireEvent.click(screen.getByRole("button", { name: /report lookup/i }));

    expect(onToolsChange).toHaveBeenCalledWith(["runsight/http", "report_lookup"]);
  });

  it("shows custom tool guidance when the API returns no custom tools", () => {
    render(
      React.createElement(SoulToolsSection as unknown as React.ComponentType<any>, {
        tools: ["runsight/http"],
        workflowTools: WORKFLOW_TOOLS.filter((tool) => tool.id !== "report_lookup"),
        availableTools: AVAILABLE_TOOLS.filter((tool) => tool.type !== "custom"),
        onToolsChange: vi.fn(),
      }),
    );

    fireEvent.click(screen.getByRole("button", { name: /tools/i }));

    expect(screen.getByText(/custom tools/i)).toBeTruthy();
    expect(screen.getByText(/custom\/tools/i)).toBeTruthy();
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
      SoulToolsSection: (props: {
        workflowTools?: WorkflowToolContext[];
        availableTools?: AvailableTool[];
      }) =>
        React.createElement(
          "section",
          { "data-testid": "workflow-tools-prop" },
          [
            ...(props.availableTools?.map((tool) =>
              React.createElement("div", { key: tool.slug }, tool.name, tool.type),
            ) ?? []),
            ...(props.workflowTools?.map((tool) =>
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
          ) ?? []),
          ],
        ),
    }));

    const { SoulFormBody } = await import("../SoulFormBody");

    render(
      React.createElement(SoulFormBody as unknown as React.ComponentType<any>, {
        values: FORM_VALUES,
        workflowTools: WORKFLOW_TOOLS,
        availableTools: AVAILABLE_TOOLS,
        setField: vi.fn(),
      }),
    );

    expect(screen.getByText("HTTP Requests")).toBeTruthy();
    expect(screen.getByText("Workspace Files")).toBeTruthy();
    expect(screen.getByText("Report Lookup")).toBeTruthy();
    expect(screen.getByText("custom")).toBeTruthy();
  });
});
