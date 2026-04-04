// @vitest-environment jsdom

import React from "react";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  setField: vi.fn(),
  submit: vi.fn(),
  reset: vi.fn(),
  workflowTools: [] as Array<{
    id: string;
    enabled: boolean;
    availableInWorkflow?: boolean;
  }>,
}));

vi.mock("react-router", () => ({
  useBlocker: () => ({ state: "unblocked", reset: vi.fn(), proceed: vi.fn() }),
  useNavigate: () => mocks.navigate,
  useParams: () => ({}),
  useSearchParams: () => [
    new URLSearchParams("return=/workflows/oss-launch-strategy/edit"),
    vi.fn(),
  ],
}));

vi.mock("@/components/shared/PageHeader", () => ({
  PageHeader: () => React.createElement("div", null, "PageHeader"),
}));

vi.mock("@/queries/souls", () => ({
  useAvailableTools: () => ({
    data: [
      {
        id: "http",
        name: "HTTP Requests",
        description: "Fetch external APIs.",
        origin: "builtin",
        executor: "native",
      },
      {
        id: "file_io",
        name: "File I/O",
        description: "Read and write files.",
        origin: "builtin",
        executor: "native",
      },
      {
        id: "delegate",
        name: "Delegate",
        description: "Delegate work.",
        origin: "builtin",
        executor: "native",
      },
    ],
  }),
  useSoul: () => ({
    data: null,
    isLoading: false,
    isError: false,
  }),
}));

vi.mock("@/queries/workflows", () => ({
  useWorkflow: () => ({
    data: {
      yaml: `version: "1.0"
tools:
  - http
  - file_io
workflow:
  name: OSS Launch Strategy
  entry: review
`,
    },
  }),
}));

vi.mock("../useSoulForm", () => ({
  useSoulForm: () => ({
    values: {
      name: "Reviewer",
      avatarColor: "warning",
      providerId: null,
      modelId: null,
      systemPrompt: "Review the strategy.",
      tools: ["file_io"],
      temperature: 0.7,
      maxTokens: null,
      maxToolIterations: 2,
    },
    isDirty: false,
    isSubmitting: false,
    reset: mocks.reset,
    setField: mocks.setField,
    submit: mocks.submit,
  }),
}));

vi.mock("../SoulFormBody", () => ({
  SoulFormBody: (props: {
    workflowTools?: Array<{
      id: string;
      enabled: boolean;
      availableInWorkflow?: boolean;
    }>;
  }) => {
    mocks.workflowTools = props.workflowTools ?? [];

    return React.createElement(
      "div",
      { "data-testid": "workflow-tools" },
      (props.workflowTools ?? []).map((tool) =>
        React.createElement(
          "div",
          { key: tool.id },
          `${tool.id}:${String(tool.enabled)}:${String(tool.availableInWorkflow !== false)}`,
        ),
      ),
    );
  },
}));

vi.mock("../SoulFormFooter", () => ({
  SoulFormFooter: () => React.createElement("div", null, "SoulFormFooter"),
}));

vi.mock("@runsight/ui/button", () => ({
  Button: ({
    children,
    ...props
  }: React.ButtonHTMLAttributes<HTMLButtonElement>) =>
    React.createElement("button", props, children),
}));

vi.mock("@runsight/ui/dialog", () => ({
  Dialog: ({
    children,
  }: React.PropsWithChildren) => React.createElement("div", null, children),
  DialogContent: ({
    children,
  }: React.PropsWithChildren) => React.createElement("div", null, children),
  DialogFooter: ({
    children,
  }: React.PropsWithChildren) => React.createElement("div", null, children),
  DialogTitle: ({
    children,
  }: React.PropsWithChildren) => React.createElement("div", null, children),
}));

describe("SoulFormPage workflow tool context", () => {
  beforeEach(() => {
    mocks.navigate.mockReset();
    mocks.setField.mockReset();
    mocks.submit.mockReset();
    mocks.reset.mockReset();
    mocks.workflowTools = [];
  });

  it("reads canonical workflow tool arrays without turning ids into numeric keys", async () => {
    const { Component } = await import("../SoulFormPage");

    render(React.createElement(Component));

    expect(screen.getByText("http:false:true")).toBeTruthy();
    expect(screen.getByText("file_io:true:true")).toBeTruthy();
    expect(mocks.workflowTools.map((tool) => tool.id)).toEqual(["http", "file_io"]);
  });
});
