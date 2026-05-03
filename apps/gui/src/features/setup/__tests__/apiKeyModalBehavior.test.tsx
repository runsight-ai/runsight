// @vitest-environment jsdom

import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const harness = vi.hoisted(() => ({
  autoTest: {
    testStatus: "idle" as "idle" | "testing" | "success" | "error",
    testMessage: "",
    models: [] as string[],
    providerId: null as string | null,
  },
  reset: vi.fn(),
  cleanup: vi.fn(),
}));

vi.mock("@/components/provider", () => ({
  ALL_PROVIDERS: [
    { id: "openai", name: "OpenAI", emoji: "O" },
    { id: "custom", name: "Custom", emoji: "C", isCustom: true },
    { id: "ollama", name: "Ollama", emoji: "L" },
  ],
}));

vi.mock("../hooks/useApiKeyAutoTest", () => ({
  useApiKeyAutoTest: () => ({
    ...harness.autoTest,
    reset: harness.reset,
    cleanup: harness.cleanup,
  }),
}));

vi.mock("../components/ConnectionFeedback", () => ({
  ConnectionFeedback: ({
    status,
    message,
    modelCount,
  }: {
    status: string;
    message: string;
    modelCount: number;
  }) => React.createElement("div", { "data-testid": "connection-feedback" }, `${status}:${message}:${modelCount}`),
}));

vi.mock("@runsight/ui/dialog", () => ({
  Dialog: ({ open, children }: { open: boolean; children?: React.ReactNode }) =>
    open ? React.createElement("div", null, children) : null,
  DialogBody: ({ children }: { children?: React.ReactNode }) => React.createElement("div", null, children),
  DialogContent: ({ children }: { children?: React.ReactNode }) => React.createElement("section", null, children),
  DialogFooter: ({ children }: { children?: React.ReactNode }) => React.createElement("footer", null, children),
  DialogHeader: ({ children }: { children?: React.ReactNode }) => React.createElement("header", null, children),
  DialogTitle: ({ children }: { children?: React.ReactNode }) => React.createElement("h2", null, children),
}));

vi.mock("@runsight/ui/select", () => {
  const optionText = (children: React.ReactNode): string =>
    React.Children.toArray(children)
      .map((child) => {
        if (typeof child === "string" || typeof child === "number") {
          return String(child);
        }
        if (React.isValidElement<{ children?: React.ReactNode }>(child)) {
          return optionText(child.props.children);
        }
        return "";
      })
      .join("");

  return {
    Select: ({
      value,
      onValueChange,
      children,
    }: {
      value: string;
      onValueChange: (value: string) => void;
      children?: React.ReactNode;
    }) =>
      React.createElement("select", {
        "aria-label": "Provider",
        value,
        onChange: (event: React.ChangeEvent<HTMLSelectElement>) => onValueChange(event.currentTarget.value),
      }, children),
    SelectContent: ({ children }: { children?: React.ReactNode }) => React.createElement(React.Fragment, null, children),
    SelectItem: ({ children, value }: { children?: React.ReactNode; value: string }) =>
      React.createElement("option", { value }, optionText(children)),
    SelectTrigger: ({ children }: { children?: React.ReactNode }) => React.createElement(React.Fragment, null, children),
    SelectValue: () => null,
  };
});

vi.mock("@runsight/ui/input", () => ({
  Input: (props: React.InputHTMLAttributes<HTMLInputElement>) => React.createElement("input", props),
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

vi.mock("@runsight/ui/label", () => ({
  Label: ({ children }: { children?: React.ReactNode }) => React.createElement("label", null, children),
}));

vi.mock("lucide-react", () => ({
  Eye: () => React.createElement("span", null, "show"),
  EyeOff: () => React.createElement("span", null, "hide"),
}));

import { ApiKeyModal } from "../ApiKeyModal";

const RESERVED_PROVIDER_BASE_URL = "https://api.example.test/v1";

beforeEach(() => {
  harness.autoTest = {
    testStatus: "idle",
    testMessage: "",
    models: [],
    providerId: null,
  };
  harness.reset.mockReset();
  harness.cleanup.mockReset();
});

afterEach(() => {
  cleanup();
});

describe("ApiKeyModal", () => {
  it("renders one-screen provider, key, feedback, and disabled save controls", () => {
    render(<ApiKeyModal open onOpenChange={vi.fn()} />);

    expect(screen.getByRole("heading", { name: "Add API Key to Run" })).toBeTruthy();
    expect(screen.getByLabelText("Provider")).toBeTruthy();
    expect(screen.getByPlaceholderText("sk-...")).toHaveAttribute("type", "password");
    expect(screen.getByTestId("connection-feedback").textContent).toBe("idle::0");
    expect((screen.getByText("Save & Run") as HTMLButtonElement).disabled).toBe(true);
  });

  it("toggles API key visibility and shows Base URL for custom providers", () => {
    const { container } = render(<ApiKeyModal open onOpenChange={vi.fn()} />);

    const apiKeyInput = screen.getByPlaceholderText("sk-...");
    fireEvent.click(screen.getByLabelText("Toggle key visibility"));
    expect(apiKeyInput).toHaveAttribute("type", "text");

    fireEvent.change(screen.getByLabelText("Provider"), { target: { value: "custom" } });

    const baseUrlInput = container.querySelector<HTMLInputElement>('input[type="url"]');
    expect(baseUrlInput).toBeTruthy();
    fireEvent.change(baseUrlInput!, { target: { value: RESERVED_PROVIDER_BASE_URL } });
    expect(baseUrlInput!.value).toBe(RESERVED_PROVIDER_BASE_URL);
    expect(harness.reset).toHaveBeenCalledTimes(1);
  });

  it("saves only after the connection test succeeds and resets on cancel", () => {
    const onOpenChange = vi.fn();
    const onSaveSuccess = vi.fn();
    harness.autoTest = {
      testStatus: "success",
      testMessage: "Connected",
      models: ["gpt-test"],
      providerId: "openai",
    };

    render(
      <ApiKeyModal
        open
        onOpenChange={onOpenChange}
        onSaveSuccess={onSaveSuccess}
      />,
    );

    fireEvent.click(screen.getByText("Save & Run"));

    expect(onSaveSuccess).toHaveBeenCalledWith("openai");
    expect(onOpenChange).toHaveBeenCalledWith(false);

    fireEvent.click(screen.getByText("Cancel"));

    expect(harness.cleanup).toHaveBeenCalledTimes(1);
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
