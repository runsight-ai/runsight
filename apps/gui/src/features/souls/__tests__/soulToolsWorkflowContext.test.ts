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
  id: string;
  name: string;
  description: string;
  origin: "builtin" | "custom";
  executor: "native" | "python" | "request";
};

const WORKFLOW_TOOLS: WorkflowToolContext[] = [
  {
    id: "http",
    label: "HTTP Requests",
    description: "Fetch external APIs.",
    enabled: true,
  },
  {
    id: "request_lookup",
    label: "Request Lookup",
    description: "Fetch live report data.",
    enabled: false,
  },
  {
    id: "python_helper",
    label: "Python Helper",
    description: "Run a local analysis helper.",
    enabled: false,
    availableInWorkflow: false,
  },
  {
    id: "delegate",
    label: "Delegate",
    description: "Delegate work to sub-agents.",
    enabled: false,
  },
];

const AVAILABLE_TOOLS: AvailableTool[] = [
  {
    id: "http",
    name: "HTTP Requests",
    description: "Fetch external APIs.",
    origin: "builtin",
    executor: "native",
  },
  {
    id: "request_lookup",
    name: "Request Lookup",
    description: "Fetch live report data.",
    origin: "custom",
    executor: "request",
  },
  {
    id: "python_helper",
    name: "Python Helper",
    description: "Run a local analysis helper.",
    origin: "custom",
    executor: "python",
  },
  {
    id: "delegate",
    name: "Delegate",
    description: "Delegate work to sub-agents.",
    origin: "builtin",
    executor: "native",
  },
];

const FORM_VALUES = {
  name: "Researcher",
  avatarColor: "accent",
  providerId: null,
  provider: null,
  modelId: null,
  systemPrompt: "Research the topic.",
  tools: ["http", "orphaned_tool"],
  temperature: 0.7,
  maxTokens: null,
  maxToolIterations: 3,
};

describe("RUN-490 workflow tool context rendering", () => {
  it("renders canonical tool metadata with workflow availability badges while keeping delegate hidden", () => {
    render(
      React.createElement(SoulToolsSection as unknown as React.ComponentType<any>, {
        tools: ["http"],
        workflowTools: WORKFLOW_TOOLS,
        availableTools: AVAILABLE_TOOLS,
        onToolsChange: vi.fn(),
      }),
    );

    fireEvent.click(screen.getByRole("button", { name: /tools/i }));

    const httpToolButton = screen.getByRole("button", { name: /http requests/i });

    expect(httpToolButton).toBeTruthy();
    expect(httpToolButton.getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByText("Request Lookup")).toBeTruthy();
    expect(screen.getByText("Python Helper")).toBeTruthy();
    expect(screen.queryByText("Delegate")).toBeNull();
    expect(screen.getByText("Request")).toBeTruthy();
    expect(screen.getByText("Python")).toBeTruthy();
    expect(screen.getByText("Available in workflow")).toBeTruthy();
    const workflowBadge = screen.getByText("Not enabled in workflow");
    expect(workflowBadge.className).toMatch(/amber|warning/i);
  });

  it("toggles canonical API tool ids when the user enables a tool", () => {
    const onToolsChange = vi.fn();

    render(
      React.createElement(SoulToolsSection as unknown as React.ComponentType<any>, {
        tools: ["http"],
        workflowTools: WORKFLOW_TOOLS,
        availableTools: AVAILABLE_TOOLS,
        onToolsChange,
      }),
    );

    fireEvent.click(screen.getByRole("button", { name: /tools/i }));
    fireEvent.click(screen.getByRole("button", { name: /request lookup/i }));

    expect(onToolsChange).toHaveBeenCalledWith(["http", "request_lookup"]);
  });

  it("shows custom tool guidance when the API returns no custom tools", () => {
    render(
      React.createElement(SoulToolsSection as unknown as React.ComponentType<any>, {
        tools: ["http"],
        workflowTools: WORKFLOW_TOOLS.filter((tool) => tool.id !== "request_lookup"),
        availableTools: AVAILABLE_TOOLS.filter((tool) => tool.origin !== "custom"),
        onToolsChange: vi.fn(),
      }),
    );

    fireEvent.click(screen.getByRole("button", { name: /tools/i }));

    expect(screen.getByText(/custom tools/i)).toBeTruthy();
    expect(screen.getByText(/custom\/tools/i)).toBeTruthy();
  });

  it("keeps selected canonical tool ids visible when the API no longer returns metadata for them", () => {
    render(
      React.createElement(SoulToolsSection as unknown as React.ComponentType<any>, {
        tools: ["http", "orphaned_tool"],
        workflowTools: WORKFLOW_TOOLS,
        availableTools: AVAILABLE_TOOLS.filter((tool) => tool.id !== "delegate"),
        onToolsChange: vi.fn(),
      }),
    );

    fireEvent.click(screen.getByRole("button", { name: /tools/i }));

    const orphanedToolButton = screen.queryByRole("button", { name: /orphaned_tool/i });

    expect(orphanedToolButton).toBeTruthy();
    expect(orphanedToolButton?.getAttribute("aria-pressed")).toBe("true");
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
              React.createElement(
                "div",
                { key: `available-${tool.id}` },
                `${tool.name}:${tool.origin}:${tool.executor}`,
              ),
            ) ?? []),
            ...(props.workflowTools?.map((tool) =>
            React.createElement(
              "div",
              { key: `workflow-${tool.id}` },
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
    expect(screen.getByText("Request Lookup:custom:request")).toBeTruthy();
    expect(screen.getByText("Python Helper:custom:python")).toBeTruthy();
  });
});
