// @vitest-environment jsdom

import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
}));

vi.mock("react-router", () => ({
  useNavigate: () => mocks.navigate,
}));

function buildWorkflow(overrides: Record<string, unknown> = {}) {
  return {
    id: "wf_research",
    name: "Research & Review",
    enabled: false,
    block_count: 3,
    modified_at: Date.parse("2026-03-31T10:00:00Z") / 1000,
    commit_sha: "f078f13deadbeef",
    health: {
      run_count: 12,
      eval_pass_pct: 92,
      eval_health: "success",
      total_cost_usd: 0.42,
      regression_count: 0,
    },
    ...overrides,
  };
}

async function loadWorkflowRowComponent() {
  const module = await import("../WorkflowRow");
  return (module.Component ??
    (module as Record<string, unknown>).WorkflowRow) as React.ComponentType<Record<string, unknown>>;
}

async function renderWorkflowRow(options: {
  workflow?: Record<string, unknown>;
  onDelete?: (workflow: unknown) => void;
  onToggleEnabled?: (...args: unknown[]) => Promise<unknown>;
} = {}) {
  const WorkflowRow = await loadWorkflowRowComponent();
  const user = userEvent.setup();

  render(
    React.createElement(
      "ul",
      { role: "list" },
      React.createElement(WorkflowRow, {
        workflow: options.workflow ?? buildWorkflow(),
        onDelete: options.onDelete ?? vi.fn(),
        onToggleEnabled: options.onToggleEnabled ?? vi.fn().mockResolvedValue(undefined),
      }),
    ),
  );

  return { user };
}

function createDeferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;

  const promise = new Promise<T>((innerResolve, innerReject) => {
    resolve = innerResolve;
    reject = innerReject;
  });

  return { promise, resolve, reject };
}

beforeEach(() => {
  mocks.navigate.mockReset();
});

afterEach(() => {
  cleanup();
});

describe("RUN-429 WorkflowRow enabled toggle", () => {
  it("renders an accessible switch that reflects the workflow enabled state", async () => {
    await renderWorkflowRow({
      workflow: buildWorkflow({ enabled: true }),
    });

    const toggle = screen.getByRole("switch", {
      name: "Enable Research & Review workflow",
    });

    expect(toggle).toHaveAttribute("aria-checked", "true");
  });

  it("toggles optimistically without navigating the workflow row", async () => {
    const onToggleEnabled = vi.fn().mockResolvedValue(undefined);
    const { user } = await renderWorkflowRow({
      workflow: buildWorkflow({ enabled: false }),
      onToggleEnabled,
    });

    const toggle = screen.getByRole("switch", {
      name: "Enable Research & Review workflow",
    });

    expect(toggle).toHaveAttribute("aria-checked", "false");

    await user.click(toggle);

    expect(onToggleEnabled).toHaveBeenCalledTimes(1);
    expect(mocks.navigate).not.toHaveBeenCalled();
    expect(toggle).toHaveAttribute("aria-checked", "true");
  });

  it("reverts the optimistic toggle state when the server update fails", async () => {
    const deferred = createDeferred<void>();
    const onToggleEnabled = vi.fn().mockImplementation(() => deferred.promise);
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const { user } = await renderWorkflowRow({
      workflow: buildWorkflow({ enabled: false }),
      onToggleEnabled,
    });

    const toggle = screen.getByRole("switch", {
      name: "Enable Research & Review workflow",
    });

    await user.click(toggle);

    expect(toggle).toHaveAttribute("aria-checked", "true");
    expect(mocks.navigate).not.toHaveBeenCalled();

    deferred.reject(new Error("workflow toggle failed"));

    await waitFor(() => {
      expect(toggle).toHaveAttribute("aria-checked", "false");
    });

    errorSpy.mockRestore();
  });
});
