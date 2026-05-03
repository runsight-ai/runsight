// @vitest-environment jsdom

import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const harness = vi.hoisted(() => ({
  createWorkflow: vi.fn(),
  updateAppSettings: vi.fn(),
  navigate: vi.fn(),
  providers: [] as Array<{ id: string; is_active?: boolean }>,
  toastError: vi.fn(),
}));

vi.mock("react-router", () => ({
  useNavigate: () => harness.navigate,
}));

vi.mock("sonner", () => ({
  toast: { error: harness.toastError },
}));

vi.mock("@/queries/workflows", () => ({
  useCreateWorkflow: () => ({
    mutateAsync: harness.createWorkflow,
    isPending: false,
  }),
}));

vi.mock("@/queries/settings", () => ({
  useUpdateAppSettings: () => ({
    mutateAsync: harness.updateAppSettings,
    isPending: false,
  }),
  useProviders: () => ({
    data: { items: harness.providers, total: harness.providers.length },
  }),
}));

vi.mock("@runsight/ui/button", () => ({
  Button: ({
    children,
    onClick,
    disabled,
  }: {
    children?: React.ReactNode;
    onClick?: () => void;
    disabled?: boolean;
  }) => React.createElement("button", { type: "button", onClick, disabled }, children),
}));

vi.mock("@runsight/ui/badge", () => ({
  Badge: ({ children }: { children?: React.ReactNode }) =>
    React.createElement("span", null, children),
}));

vi.mock("@runsight/ui/input", () => ({
  Input: (props: React.InputHTMLAttributes<HTMLInputElement>) =>
    React.createElement("input", props),
}));

vi.mock("@runsight/ui/label", () => ({
  Label: ({
    children,
    htmlFor,
  }: {
    children?: React.ReactNode;
    htmlFor?: string;
  }) => React.createElement("label", { htmlFor }, children),
}));

vi.mock("../components/SelectionCard", () => ({
  SelectionCard: ({
    selected,
    onSelect,
    label,
    title,
    children,
  }: {
    selected: boolean;
    onSelect: () => void;
    label: string;
    title: string;
    children?: React.ReactNode;
  }) =>
    React.createElement(
      "button",
      { type: "button", role: "radio", "aria-checked": selected, "aria-label": label, onClick: onSelect },
      [title, children],
    ),
}));

vi.mock("../components/MiniDiagram", () => ({
  MiniDiagram: () => React.createElement("span", null, "template-preview"),
}));

vi.mock("../components/EmptyCanvasPreview", () => ({
  EmptyCanvasPreview: () => React.createElement("span", null, "blank-preview"),
}));

vi.mock("lucide-react", () => ({
  Plus: () => React.createElement("span", null),
  Workflow: () => React.createElement("span", null),
  Play: () => React.createElement("span", null),
}));

import { Component as SetupStartPage } from "../SetupStartPage";

beforeEach(() => {
  harness.createWorkflow.mockReset();
  harness.createWorkflow.mockResolvedValue({ id: "wf_created" });
  harness.updateAppSettings.mockReset();
  harness.updateAppSettings.mockResolvedValue({});
  harness.navigate.mockReset();
  harness.providers = [];
  harness.toastError.mockReset();
});

afterEach(() => {
  cleanup();
});

describe("SetupStartPage flow", () => {
  it("starts on the template option and shows explore mode without providers", () => {
    render(<SetupStartPage />);

    expect(screen.getByRole("heading", { name: "How do you want to start?" })).toBeTruthy();
    expect(screen.getByRole("radio", { name: "Start with a template" }).getAttribute("aria-checked")).toBe("true");
    expect(screen.getByText("Explore mode")).toBeTruthy();
  });

  it("creates the template workflow, completes onboarding, and navigates to the editor", async () => {
    render(<SetupStartPage />);

    fireEvent.click(screen.getByText("Start Building"));

    await waitFor(() => {
      expect(harness.createWorkflow).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Research & Review",
          commit: false,
          yaml: expect.stringContaining("kind: workflow"),
        }),
      );
    });
    expect(harness.updateAppSettings).toHaveBeenCalledWith({ onboarding_completed: true });
    expect(harness.navigate).toHaveBeenCalledWith("/workflows/wf_created/edit", { replace: true });
  });

  it("validates blank workflow ids before creating", async () => {
    render(<SetupStartPage />);

    fireEvent.click(screen.getByRole("radio", { name: "Start with a blank canvas" }));
    fireEvent.change(screen.getByLabelText("Workflow id"), { target: { value: "Bad ID" } });

    expect((screen.getByText("Start Building") as HTMLButtonElement).disabled).toBe(true);

    fireEvent.change(screen.getByLabelText("Workflow id"), { target: { value: "blank-flow" } });
    fireEvent.change(screen.getByLabelText("Workflow name"), { target: { value: "Blank Flow" } });
    fireEvent.click(screen.getByText("Start Building"));

    await waitFor(() => {
      expect(harness.createWorkflow).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Blank Flow",
          yaml: expect.stringContaining("id: blank-flow"),
        }),
      );
    });
  });
});
