// @vitest-environment jsdom

import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AppSettings, FallbackTarget, Provider } from "@/api/settings";

const harness = vi.hoisted(() => ({
  fallbackState: {
    data: undefined as { items: FallbackTarget[]; total: number } | undefined,
    isLoading: false,
    error: null as Error | null,
    refetch: vi.fn(),
  },
  providersState: {
    data: undefined as { items: Provider[]; total: number } | undefined,
  },
  appSettingsState: {
    data: undefined as AppSettings | undefined,
  },
  updateFallbackTarget: {
    mutateAsync: vi.fn(),
    isPending: false,
  },
  updateAppSettings: {
    mutateAsync: vi.fn(),
    isPending: false,
  },
}));

vi.mock("@/queries/settings", () => ({
  useFallbackTargets: () => harness.fallbackState,
  useProviders: () => harness.providersState,
  useAppSettings: () => harness.appSettingsState,
  useUpdateFallbackTarget: () => harness.updateFallbackTarget,
  useUpdateAppSettings: () => harness.updateAppSettings,
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock("@runsight/ui/empty-state", () => ({
  EmptyState: ({ title, description }: { title: string; description: string }) => (
    <div>
      <h2>{title}</h2>
      <p>{description}</p>
    </div>
  ),
}));

vi.mock("@runsight/ui/switch", () => ({
  Switch: ({
    checked,
    disabled,
    className: _className,
    onCheckedChange,
    wrapperClassName: _wrapperClassName,
    ...props
  }: {
    checked?: boolean;
    disabled?: boolean;
    className?: string;
    onCheckedChange?: (checked: boolean) => void;
    wrapperClassName?: string;
    [key: string]: unknown;
  }) => (
    <button
      type="button"
      role="switch"
      aria-checked={checked ? "true" : "false"}
      disabled={disabled}
      onClick={() => {
        if (!disabled) onCheckedChange?.(!checked);
      }}
      {...props}
    />
  ),
}));

vi.mock("@runsight/ui/select", () => {
  function textFrom(children: React.ReactNode): string {
    return React.Children.toArray(children)
      .map((child) => {
        if (typeof child === "string" || typeof child === "number") return String(child);
        if (React.isValidElement<{ children?: React.ReactNode }>(child)) {
          return textFrom(child.props.children);
        }
        return "";
      })
      .join("");
  }

  function SelectTrigger(_props: { children?: React.ReactNode }) {
    return null;
  }

  function SelectContent(_props: { children?: React.ReactNode }) {
    return null;
  }

  function SelectValue(_props: { placeholder?: string }) {
    return null;
  }

  function SelectItem(_props: { children?: React.ReactNode; value: string }) {
    return null;
  }

  function findTrigger(children: React.ReactNode): Record<string, unknown> {
    for (const child of React.Children.toArray(children)) {
      if (!React.isValidElement(child)) continue;
      if (child.type === SelectTrigger) return child.props as Record<string, unknown>;
      const nested = findTrigger((child.props as { children?: React.ReactNode }).children);
      if (Object.keys(nested).length > 0) return nested;
    }
    return {};
  }

  function collectItems(children: React.ReactNode): Array<{ value: string; label: string }> {
    const items: Array<{ value: string; label: string }> = [];
    for (const child of React.Children.toArray(children)) {
      if (!React.isValidElement(child)) continue;
      if (child.type === SelectItem) {
        const props = child.props as { children?: React.ReactNode; value: string };
        items.push({ value: props.value, label: textFrom(props.children) });
        continue;
      }
      items.push(...collectItems((child.props as { children?: React.ReactNode }).children));
    }
    return items;
  }

  function Select({
    value,
    disabled,
    onValueChange,
    children,
  }: {
    value?: string;
    disabled?: boolean;
    onValueChange: (value: string) => void;
    children?: React.ReactNode;
  }) {
    const trigger = findTrigger(children);
    const items = collectItems(children);
    const placeholder = textFrom((trigger.children as React.ReactNode) ?? "Select");

    return (
      <select
        aria-label={trigger["aria-label"] as string}
        value={value ?? ""}
        disabled={disabled}
        onChange={(event) => onValueChange(event.currentTarget.value)}
      >
        <option value="">{placeholder || "Select"}</option>
        {items.map((item) => (
          <option key={item.value} value={item.value}>
            {item.label}
          </option>
        ))}
      </select>
    );
  }

  return {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
  };
});

import { ModelsTab } from "../ModelsTab";

function buildProvider(overrides: Partial<Provider> = {}): Provider {
  return {
    id: "openai",
    name: "OpenAI",
    provider: "openai",
    status: "connected",
    api_key_preview: "sk-...abcd",
    api_key_env: null,
    base_url: null,
    models: ["gpt-4o", "gpt-5"],
    is_active: true,
    ...overrides,
  } as Provider;
}

function buildFallbackTarget(overrides: Partial<FallbackTarget> = {}): FallbackTarget {
  return {
    id: "openai",
    provider_id: "openai",
    provider_name: "OpenAI",
    fallback_provider_id: "anthropic",
    fallback_provider_name: "Anthropic",
    fallback_model_id: "claude-haiku",
    ...overrides,
  } as FallbackTarget;
}

function createDeferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  const promise = new Promise<T>((innerResolve) => {
    resolve = innerResolve;
  });
  return { promise, resolve };
}

beforeEach(() => {
  harness.providersState = {
    data: {
      items: [
        buildProvider(),
        buildProvider({
          id: "anthropic",
          name: "Anthropic",
          provider: "anthropic",
          models: ["claude-haiku", "claude-sonnet"],
        }),
      ],
      total: 2,
    },
  };
  harness.fallbackState = {
    data: { items: [buildFallbackTarget()], total: 1 },
    isLoading: false,
    error: null,
    refetch: vi.fn().mockResolvedValue(undefined),
  };
  harness.appSettingsState = {
    data: { fallback_enabled: true } as AppSettings,
  };
  harness.updateFallbackTarget = {
    mutateAsync: vi.fn().mockResolvedValue(undefined),
    isPending: false,
  };
  harness.updateAppSettings = {
    mutateAsync: vi.fn().mockResolvedValue(undefined),
    isPending: false,
  };
});

describe("Settings fallback behavior", () => {
  it("renders the full-page no-provider state when no providers are configured", () => {
    harness.providersState.data = { items: [], total: 0 };

    render(<ModelsTab />);

    expect(screen.getByRole("heading", { name: "No providers configured" })).toBeTruthy();
    expect(screen.getByText("Connect at least one provider to manage runtime fallback.")).toBeTruthy();
  });

  it("disables fallback configuration until at least two providers are enabled", () => {
    harness.providersState.data = {
      items: [
        buildProvider(),
        buildProvider({
          id: "anthropic",
          name: "Anthropic",
          provider: "anthropic",
          is_active: false,
        }),
      ],
      total: 2,
    };

    render(<ModelsTab />);

    expect(screen.getByRole("switch", { name: "Enable fallback" })).toBeTruthy();
    expect((screen.getByRole("switch", { name: "Enable fallback" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText("Fallback unavailable")).toBeTruthy();
    expect(screen.getByText(/Enable at least two providers to configure runtime fallback/)).toBeTruthy();
  });

  it("renders one fallback row per target with sibling providers and selected-provider models", () => {
    render(<ModelsTab />);

    const providerSelect = screen.getByRole("combobox", { name: "Fallback provider for OpenAI" });
    const modelSelect = screen.getByRole("combobox", { name: "Fallback model for OpenAI" });

    expect(screen.getByText("OpenAI")).toBeTruthy();
    expect(providerSelect).toHaveValue("Anthropic");
    expect(modelSelect).toHaveValue("claude-haiku");
    expect(providerSelect.textContent).toContain("Anthropic");
    expect(providerSelect.textContent).not.toContain("OpenAI");
    expect(modelSelect.textContent).toContain("claude-haiku");
    expect(modelSelect.textContent).toContain("claude-sonnet");
    expect(screen.getByRole("button", { name: "Clear fallback for OpenAI" })).toBeTruthy();
  });

  it("toggles fallback persistence and disables row controls while fallback is off", async () => {
    const user = userEvent.setup();
    harness.appSettingsState.data = { fallback_enabled: false } as AppSettings;

    render(<ModelsTab />);

    expect(screen.getByRole("switch", { name: "Enable fallback" }).getAttribute("aria-checked")).toBe("false");
    expect((screen.getByRole("combobox", { name: "Fallback provider for OpenAI" }) as HTMLSelectElement).disabled).toBe(true);
    expect((screen.getByRole("combobox", { name: "Fallback model for OpenAI" }) as HTMLSelectElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "Clear fallback for OpenAI" }) as HTMLButtonElement).disabled).toBe(true);

    await user.click(screen.getByRole("switch", { name: "Enable fallback" }));

    expect(harness.updateAppSettings.mutateAsync).toHaveBeenCalledWith({ fallback_enabled: true });
  });

  it("resets the model when the fallback provider changes and commits only after a model is selected", async () => {
    const user = userEvent.setup();
    harness.providersState.data = {
      items: [
        buildProvider(),
        buildProvider({
          id: "anthropic",
          name: "Anthropic",
          provider: "anthropic",
          models: ["claude-haiku"],
        }),
        buildProvider({
          id: "ollama",
          name: "Ollama",
          provider: "ollama",
          models: ["llama3", "mistral"],
        }),
      ],
      total: 3,
    };

    render(<ModelsTab />);

    const providerSelect = screen.getByRole("combobox", { name: "Fallback provider for OpenAI" });
    const modelSelect = screen.getByRole("combobox", { name: "Fallback model for OpenAI" });

    await user.selectOptions(providerSelect, "Ollama");

    expect(harness.updateFallbackTarget.mutateAsync).not.toHaveBeenCalled();
    expect(modelSelect).toHaveValue("");
    expect(modelSelect.textContent).toContain("llama3");
    expect(modelSelect.textContent).toContain("mistral");

    await user.selectOptions(modelSelect, "llama3");

    expect(harness.updateFallbackTarget.mutateAsync).toHaveBeenCalledWith({
      id: "openai",
      data: {
        fallback_provider_id: "ollama",
        fallback_model_id: "llama3",
      },
    });
  });

  it("clears fallback provider and model together from the row clear action", async () => {
    const user = userEvent.setup();

    render(<ModelsTab />);

    await user.click(screen.getByRole("button", { name: "Clear fallback for OpenAI" }));

    expect(harness.updateFallbackTarget.mutateAsync).toHaveBeenCalledWith({
      id: "openai",
      data: {
        fallback_provider_id: "",
        fallback_model_id: "",
      },
    });
  });

  it("renders fallback query errors and keeps retry disabled while refetch is pending", async () => {
    const retry = createDeferred<void>();
    harness.fallbackState = {
      data: undefined,
      isLoading: false,
      error: new Error("Fallback service unavailable"),
      refetch: vi.fn().mockReturnValue(retry.promise),
    };

    render(<ModelsTab />);

    expect(screen.getByRole("heading", { name: "Failed to load fallback settings" })).toBeTruthy();
    expect(screen.getByText("Fallback service unavailable")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    expect(screen.getByRole("button", { name: "Retrying..." })).toBeTruthy();
    expect((screen.getByRole("button", { name: "Retrying..." }) as HTMLButtonElement).disabled).toBe(true);
    expect(harness.fallbackState.refetch).toHaveBeenCalledTimes(1);

    retry.resolve();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Retry" })).toBeTruthy();
    });
  });
});
