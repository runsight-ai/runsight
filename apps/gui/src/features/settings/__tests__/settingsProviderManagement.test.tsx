// @vitest-environment jsdom

import React from "react";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Provider } from "@/api/settings";

const harness = vi.hoisted(() => ({
  providersState: {
    data: undefined as { items: Provider[]; total: number } | undefined,
    isLoading: false,
    error: null as Error | null,
    refetch: vi.fn(),
  },
  deleteProvider: {
    mutate: vi.fn(),
    isPending: false,
  },
  testProviderConnection: {
    mutateAsync: vi.fn(),
  },
  updateProvider: {
    mutate: vi.fn(),
  },
}));

vi.mock("@/queries/settings", () => ({
  useProviders: () => harness.providersState,
  useDeleteProvider: () => harness.deleteProvider,
  useTestProviderConnection: () => harness.testProviderConnection,
  useUpdateProvider: () => harness.updateProvider,
}));

vi.mock("../AddProviderDialog", () => ({
  AddProviderDialog: ({ open }: { open: boolean }) =>
    open ? <div role="dialog" aria-label="Provider form" /> : null,
}));

vi.mock("@runsight/ui/dialog", () => ({
  Dialog: ({ open, children }: { open: boolean; children?: React.ReactNode }) =>
    open ? <>{children}</> : null,
  DialogContent: ({ children }: { children?: React.ReactNode }) => (
    <section role="dialog" aria-modal="true">
      {children}
    </section>
  ),
  DialogDescription: ({ children }: { children?: React.ReactNode }) => <p>{children}</p>,
  DialogFooter: ({ children }: { children?: React.ReactNode }) => <footer>{children}</footer>,
  DialogHeader: ({ children }: { children?: React.ReactNode }) => <header>{children}</header>,
  DialogTitle: ({ children }: { children?: React.ReactNode }) => <h2>{children}</h2>,
}));

vi.mock("@runsight/ui/empty-state", () => ({
  EmptyState: ({
    title,
    description,
    action,
  }: {
    title: string;
    description: string;
    action?: { label: string; onClick: () => void };
  }) => (
    <div>
      <h2>{title}</h2>
      <p>{description}</p>
      {action ? (
        <button type="button" onClick={action.onClick}>
          {action.label}
        </button>
      ) : null}
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

import { ProvidersTab } from "../ProvidersTab";

function buildProvider(overrides: Partial<Provider> = {}): Provider {
  return {
    id: "openai",
    name: "OpenAI",
    provider: "openai",
    status: "connected",
    api_key_preview: "sk-...abcd",
    api_key_env: null,
    base_url: "https://api.openai.test/v1",
    models: ["gpt-4o", "gpt-5"],
    is_active: true,
    ...overrides,
  } as Provider;
}

function renderProvidersTab(props: Partial<React.ComponentProps<typeof ProvidersTab>> = {}) {
  return render(
    <ProvidersTab
      onAddProvider={props.onAddProvider ?? vi.fn()}
      onEditProvider={props.onEditProvider ?? vi.fn()}
      dialogOpen={props.dialogOpen ?? false}
      onDialogOpenChange={props.onDialogOpenChange ?? vi.fn()}
      editing={props.editing}
    />,
  );
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
    data: { items: [buildProvider()], total: 1 },
    isLoading: false,
    error: null,
    refetch: vi.fn().mockResolvedValue(undefined),
  };
  harness.deleteProvider = {
    mutate: vi.fn((_id: string, options?: { onSuccess?: () => void }) => options?.onSuccess?.()),
    isPending: false,
  };
  harness.testProviderConnection = {
    mutateAsync: vi.fn().mockResolvedValue(undefined),
  };
  harness.updateProvider = {
    mutate: vi.fn(),
  };
});

describe("Settings provider management", () => {
  it("renders provider rows with accessible status, toggle, and row actions", async () => {
    const user = userEvent.setup();
    const onEditProvider = vi.fn();

    renderProvidersTab({ onEditProvider });

    expect(screen.getByRole("columnheader", { name: "Provider" })).toBeTruthy();
    expect(screen.getByText("OpenAI")).toBeTruthy();
    expect(screen.getByText("sk-...abcd")).toBeTruthy();
    expect(screen.getByLabelText("Provider OpenAI status Connected")).toBeTruthy();
    expect(screen.getByText("2 models")).toBeTruthy();

    const enabledSwitch = screen.getByRole("switch", { name: "Enable OpenAI provider" });
    expect(enabledSwitch.getAttribute("aria-checked")).toBe("true");

    await user.click(enabledSwitch);

    expect(harness.updateProvider.mutate).toHaveBeenCalledWith({
      id: "openai",
      data: { id: "openai", kind: "provider", is_active: false },
    });

    await user.click(screen.getByRole("button", { name: "Edit OpenAI provider" }));
    expect(onEditProvider).toHaveBeenCalledWith(expect.objectContaining({ id: "openai" }));
  });

  it("runs connection tests through the row action and exposes the pending label", async () => {
    const user = userEvent.setup();
    const pendingTest = createDeferred<void>();
    harness.testProviderConnection.mutateAsync = vi.fn().mockReturnValue(pendingTest.promise);

    renderProvidersTab();

    await user.click(screen.getByRole("button", { name: "Test OpenAI connection" }));

    const testButton = screen.getByRole("button", { name: "Test OpenAI connection" });
    expect(testButton.textContent).toContain("Testing...");
    expect((testButton as HTMLButtonElement).disabled).toBe(true);
    expect(harness.testProviderConnection.mutateAsync).toHaveBeenCalledWith("openai");

    pendingTest.resolve();

    await waitFor(() => {
      expect(testButton.textContent).toContain("Test");
    });
  });

  it("opens a rendered delete dialog, cancels it, and confirms the selected provider id", async () => {
    const user = userEvent.setup();
    harness.providersState.data = {
      items: [buildProvider({ id: "anthropic", name: "Anthropic", status: "error" })],
      total: 1,
    };

    renderProvidersTab();

    await user.click(screen.getByRole("button", { name: "Delete Anthropic provider" }));

    let dialog = screen.getByRole("dialog");
    expect(within(dialog).getByRole("heading", { name: "Delete Provider" })).toBeTruthy();
    expect(within(dialog).getByText(/Anthropic/)).toBeTruthy();

    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).toBeNull();
    });

    await user.click(screen.getByRole("button", { name: "Delete Anthropic provider" }));

    dialog = screen.getByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Delete" }));

    expect(harness.deleteProvider.mutate).toHaveBeenCalledWith(
      "anthropic",
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    );
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).toBeNull();
    });
  });

  it("renders the empty provider state with an add-provider action", async () => {
    const user = userEvent.setup();
    const onAddProvider = vi.fn();
    harness.providersState.data = { items: [], total: 0 };

    renderProvidersTab({ onAddProvider });

    expect(screen.getByRole("heading", { name: "No providers configured" })).toBeTruthy();
    expect(screen.getByText(/Add an AI provider to start using Runsight/)).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Add Provider" }));

    expect(onAddProvider).toHaveBeenCalledTimes(1);
  });

  it("renders provider query errors and keeps retry disabled while refetch is pending", async () => {
    const retry = createDeferred<void>();
    harness.providersState = {
      data: undefined,
      isLoading: false,
      error: new Error("Provider service unavailable"),
      refetch: vi.fn().mockReturnValue(retry.promise),
    };

    renderProvidersTab();

    expect(screen.getByRole("heading", { name: "Failed to load providers" })).toBeTruthy();
    expect(screen.getByText("Provider service unavailable")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    expect(screen.getByRole("button", { name: "Retrying..." })).toBeTruthy();
    expect((screen.getByRole("button", { name: "Retrying..." }) as HTMLButtonElement).disabled).toBe(true);
    expect(harness.providersState.refetch).toHaveBeenCalledTimes(1);

    retry.resolve();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Retry" })).toBeTruthy();
    });
  });
});
