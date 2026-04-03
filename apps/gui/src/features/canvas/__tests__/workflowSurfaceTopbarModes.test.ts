// @vitest-environment jsdom

import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const GUI_SRC_ROOT = resolve(import.meta.dirname, "../../..");
const TOPBAR_MODULE_PATH = resolve(
  GUI_SRC_ROOT,
  "features/canvas/WorkflowSurfaceTopbar.tsx",
);

function readSource(relativePath: string) {
  return readFileSync(resolve(GUI_SRC_ROOT, relativePath), "utf8");
}

async function loadWorkflowSurfaceTopbar() {
  expect(existsSync(TOPBAR_MODULE_PATH)).toBe(true);
  const module = (await import(pathToFileURL(TOPBAR_MODULE_PATH).href)) as Record<
    string,
    unknown
  >;
  const component =
    module.WorkflowSurfaceTopbar
    ?? module.Component
    ?? module.default;

  expect(typeof component).toBe("function");
  return component as React.ComponentType<Record<string, unknown>>;
}

afterEach(() => {
  cleanup();
});

describe("RUN-594 shared workflow surface topbar", () => {
  it("adds a shared WorkflowSurfaceTopbar module and routes both workflow and run pages through it instead of mounting separate page-specific topbars", () => {
    expect(existsSync(TOPBAR_MODULE_PATH)).toBe(true);

    const canvasPageSource = readSource("features/canvas/CanvasPage.tsx");
    const runDetailSource = readSource("features/runs/RunDetail.tsx");

    expect(canvasPageSource).toMatch(/WorkflowSurfaceTopbar/);
    expect(runDetailSource).toMatch(/WorkflowSurfaceTopbar/);
    expect(canvasPageSource).not.toMatch(/topbar=\{<CanvasTopbar/);
    expect(runDetailSource).not.toMatch(/topbar=\{<RunDetailHeader/);
  });

  it("shows editable workflow controls in workflow mode without run-only metrics or historical actions", async () => {
    const WorkflowSurfaceTopbar = await loadWorkflowSurfaceTopbar();

    render(
      React.createElement(WorkflowSurfaceTopbar, {
        mode: "workflow",
        workflowName: "Research Workflow",
        activeTab: "yaml",
        onTabChange: vi.fn(),
        isDirty: true,
        onSave: vi.fn(),
        onRun: vi.fn(),
      }),
    );

    expect(screen.getByText("Research Workflow")).not.toBeNull();
    expect(screen.getByRole("button", { name: /save/i })).not.toBeNull();
    expect(screen.getByRole("tab", { name: /canvas/i })).not.toBeNull();
    expect(screen.getByRole("tab", { name: /yaml/i })).not.toBeNull();
    expect(screen.queryByText(/Total Cost/i)).toBeNull();
    expect(screen.queryByRole("button", { name: /fork/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /open workflow/i })).toBeNull();
  });

  it("shows run metadata and historical actions in historical mode while hiding workflow-only controls", async () => {
    const WorkflowSurfaceTopbar = await loadWorkflowSurfaceTopbar();

    render(
      React.createElement(WorkflowSurfaceTopbar, {
        mode: "historical",
        workflowName: "Research Workflow",
        run: {
          id: "run_hist_123456",
          workflow_id: "wf-research",
          status: "completed",
        },
        metrics: {
          total_cost_usd: 1.234,
          total_tokens: 1234,
        },
        onFork: vi.fn(),
        onOpenWorkflow: vi.fn(),
        hasSnapshot: true,
      }),
    );

    expect(screen.getByText(/Read-only review/i)).not.toBeNull();
    expect(screen.getByText(/Total Cost/i)).not.toBeNull();
    expect(screen.getByText(/Tokens/i)).not.toBeNull();
    expect(screen.getByRole("button", { name: /fork/i })).not.toBeNull();
    expect(screen.getByRole("button", { name: /open workflow/i })).not.toBeNull();
    expect(screen.queryByRole("button", { name: /save/i })).toBeNull();
    expect(screen.queryByRole("tab", { name: /yaml/i })).toBeNull();
  });

  it("keeps execution mode on the same topbar component while exposing live run metadata and suppressing historical-only actions", async () => {
    const WorkflowSurfaceTopbar = await loadWorkflowSurfaceTopbar();

    render(
      React.createElement(WorkflowSurfaceTopbar, {
        mode: "execution",
        workflowName: "Research Workflow",
        run: {
          id: "run_exec_123456",
          workflow_id: "wf-research",
          status: "running",
        },
        metrics: {
          total_cost_usd: 0.128,
          total_tokens: 512,
        },
        onOpenWorkflow: vi.fn(),
      }),
    );

    expect(screen.getByText(/running/i)).not.toBeNull();
    expect(screen.getByText(/Total Cost/i)).not.toBeNull();
    expect(screen.getByText(/Tokens/i)).not.toBeNull();
    expect(screen.queryByRole("button", { name: /fork/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /save/i })).toBeNull();
  });

  it("keeps fork-draft mode on the shared topbar with editable workflow actions", async () => {
    const WorkflowSurfaceTopbar = await loadWorkflowSurfaceTopbar();

    render(
      React.createElement(WorkflowSurfaceTopbar, {
        mode: "fork-draft",
        workflowName: "Draft Workflow",
        activeTab: "canvas",
        onTabChange: vi.fn(),
        onSave: vi.fn(),
        onRun: vi.fn(),
      }),
    );

    expect(screen.getByText("Draft Workflow")).not.toBeNull();
    expect(screen.getByRole("button", { name: /save/i })).not.toBeNull();
    expect(screen.getByRole("tab", { name: /canvas/i })).not.toBeNull();
    expect(screen.queryByText(/Read-only review/i)).toBeNull();
    expect(screen.queryByRole("button", { name: /fork/i })).toBeNull();
  });

  it("disables historical fork when the snapshot is unavailable while preserving the shared topbar component", async () => {
    const WorkflowSurfaceTopbar = await loadWorkflowSurfaceTopbar();

    render(
      React.createElement(WorkflowSurfaceTopbar, {
        mode: "historical",
        workflowName: "Research Workflow",
        run: {
          id: "run_hist_654321",
          workflow_id: "wf-research",
          status: "completed",
        },
        metrics: {
          total_cost_usd: 0.5,
          total_tokens: 400,
        },
        hasSnapshot: false,
        onFork: vi.fn(),
        onOpenWorkflow: vi.fn(),
      }),
    );

    const forkButton = screen.getByRole("button", { name: /fork/i });
    expect(forkButton).toBeDisabled();
    expect(forkButton).toHaveAttribute("title", "Snapshot unavailable");
  });
});
