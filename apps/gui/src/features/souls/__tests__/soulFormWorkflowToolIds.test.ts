// @vitest-environment jsdom

import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  blockerProceed: vi.fn(),
  blockerReset: vi.fn(),
  blockerState: "unblocked" as "blocked" | "unblocked",
  isDirty: false,
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
  useBlocker: () => ({
    state: mocks.blockerState,
    reset: mocks.blockerReset,
    proceed: mocks.blockerProceed,
  }),
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
  useSoulForm: (options: { onSuccess?: (soul: { id: string }) => void }) => ({
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
    isDirty: mocks.isDirty,
    isSubmitting: false,
    reset: mocks.reset,
    setField: mocks.setField,
    submit: async () => {
      mocks.submit();
      options.onSuccess?.({ id: "reviewer" });
    },
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
  SoulFormFooter: ({
    mode,
    returnUrl,
    onCancel,
    onSubmit,
  }: {
    mode: "create" | "edit";
    returnUrl: string | null;
    onCancel: () => void;
    onSubmit: () => void;
  }) =>
    React.createElement(
      "footer",
      null,
      React.createElement("button", { type: "button", onClick: onCancel }, "Cancel"),
      React.createElement(
        "button",
        { type: "button", onClick: onSubmit },
        returnUrl ? "Save & Return to Canvas" : mode === "create" ? "Create Soul" : "Save Changes",
      ),
    ),
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
    open,
    children,
  }: React.PropsWithChildren<{ open?: boolean }>) =>
    open ? React.createElement("div", null, children) : null,
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
    mocks.blockerProceed.mockReset();
    mocks.blockerReset.mockReset();
    mocks.blockerState = "unblocked";
    mocks.isDirty = false;
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

  it("returns to the workflow editor after saving a soul opened from canvas", async () => {
    const { Component } = await import("../SoulFormPage");

    render(React.createElement(Component));

    fireEvent.click(screen.getByRole("button", { name: "Save & Return to Canvas" }));

    await waitFor(() => {
      expect(mocks.submit).toHaveBeenCalledTimes(1);
      expect(mocks.navigate).toHaveBeenCalledWith(
        "/workflows/oss-launch-strategy/edit",
      );
    });
  });

  it("shows discard and keep-editing controls when dirty navigation is blocked", async () => {
    mocks.blockerState = "blocked";
    mocks.isDirty = true;
    const { Component } = await import("../SoulFormPage");

    render(React.createElement(Component));

    fireEvent.click(screen.getByRole("button", { name: "Keep editing" }));
    fireEvent.click(screen.getByRole("button", { name: "Discard changes" }));

    expect(mocks.blockerReset).toHaveBeenCalledTimes(1);
    expect(mocks.blockerProceed).toHaveBeenCalledTimes(1);
  });
});
