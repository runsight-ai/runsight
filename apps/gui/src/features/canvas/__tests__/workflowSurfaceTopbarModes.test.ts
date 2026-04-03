// @vitest-environment jsdom

import { readdirSync, readFileSync } from "node:fs";
import { extname, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const GUI_SRC_ROOT = resolve(import.meta.dirname, "../../..");

function collectSourceFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const fullPath = resolve(dir, entry.name);

    if (entry.isDirectory()) {
      if (entry.name === "__tests__") {
        return [];
      }

      return collectSourceFiles(fullPath);
    }

    const extension = extname(entry.name);
    if (![".ts", ".tsx"].includes(extension) || entry.name.endsWith(".d.ts")) {
      return [];
    }

    return [fullPath];
  });
}

function candidateSharedTopbarModules() {
  return collectSourceFiles(GUI_SRC_ROOT).filter((filePath) => {
    const source = readFileSync(filePath, "utf8");

    return (
      filePath.endsWith(".tsx")
      && /workflowName|workflow_name/.test(source)
      && /mode/.test(source)
      && source.includes("workflow")
      && source.includes("execution")
      && source.includes("historical")
      && source.includes("fork-draft")
      && /save|fork|openWorkflow|open workflow/i.test(source)
      && /Total Cost|Tokens|Read-only review|Canvas|YAML/i.test(source)
      && /<header|<Button|<Tabs|button/i.test(source)
      && /export\s+(function|const)\s+[A-Z][A-Za-z0-9]*|export\s+default/.test(source)
    );
  });
}

async function loadSharedTopbarComponent() {
  const candidates = candidateSharedTopbarModules();

  expect(candidates.length).toBeGreaterThan(0);

  for (const candidate of candidates) {
    const module = (await import(pathToFileURL(candidate).href)) as Record<string, unknown>;

    for (const [key, value] of Object.entries(module)) {
      if ((key === "default" || /^[A-Z]/.test(key)) && typeof value === "function") {
        return value as React.ComponentType<Record<string, unknown>>;
      }
    }
  }

  throw new Error("Expected a reusable shared topbar component for workflow surface modes");
}

function buildRun(status: "completed" | "failed" | "running" | "pending" | "success" | "error") {
  return {
    id: "run_123456",
    workflow_id: "wf-research",
    workflow_name: "Research Workflow",
    status,
    total_cost_usd: 1.234,
    total_tokens: 1234,
    duration_seconds: 45,
    started_at: 1700000000,
    completed_at: 1700000045,
    created_at: 1700000000,
    commit_sha: status === "pending" ? null : "abc123",
  };
}

afterEach(() => {
  cleanup();
  vi.resetModules();
  vi.unmock("react-router");
  vi.unmock("@tanstack/react-query");
  vi.unmock("@/components/shared/PriorityBanner");
  vi.unmock("@/components/shared");
  vi.unmock("@/components/shared/ErrorBoundary");
  vi.unmock("@/components/provider/ProviderModal");
  vi.unmock("@/features/git/CommitDialog");
  vi.unmock("@/api/git");
  vi.unmock("@/queries/runs");
  vi.unmock("@/queries/settings");
  vi.unmock("@/queries/git");
  vi.unmock("@/store/canvas");
  vi.unmock("@/features/canvas/workflowSurfaceQueries");
  vi.unmock("@/features/canvas/WorkflowEditorSurface");
  vi.unmock("@/features/canvas/ForkDraftWorkflowSurface");
  vi.unmock("@/features/runs/HistoricalWorkflowSurface");
  vi.unmock("@runsight/ui/dialog");
  vi.unmock("@runsight/ui/button");
  vi.unmock("@runsight/ui/empty-state");
  vi.unmock("@runsight/ui/card");
  vi.unmock("@xyflow/react");
  vi.unmock("lucide-react");
});

describe("RUN-594 shared workflow surface topbar", () => {
  it("introduces one reusable topbar component family that can express workflow, execution, historical, and fork-draft states", async () => {
    await loadSharedTopbarComponent();
  });

  it("shows editable workflow controls in workflow mode without run-only metrics or historical actions", async () => {
    const SharedTopbar = await loadSharedTopbarComponent();

    render(
      React.createElement(SharedTopbar, {
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
    const SharedTopbar = await loadSharedTopbarComponent();

    render(
      React.createElement(SharedTopbar, {
        mode: "historical",
        workflowName: "Research Workflow",
        run: buildRun("completed"),
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

  it("keeps execution and post-terminal workflow states on the same topbar component family", async () => {
    const SharedTopbar = await loadSharedTopbarComponent();

    const { rerender } = render(
      React.createElement(SharedTopbar, {
        mode: "execution",
        workflowName: "Research Workflow",
        run: buildRun("running"),
        metrics: {
          total_cost_usd: 0.128,
          total_tokens: 512,
        },
      }),
    );

    expect(screen.getByText(/running/i)).not.toBeNull();
    expect(screen.getByText(/Total Cost/i)).not.toBeNull();
    expect(screen.queryByRole("button", { name: /save/i })).toBeNull();

    rerender(
      React.createElement(SharedTopbar, {
        mode: "workflow",
        workflowName: "Research Workflow",
        activeTab: "yaml",
        onTabChange: vi.fn(),
        onSave: vi.fn(),
        onRun: vi.fn(),
      }),
    );

    expect(screen.getByText("Research Workflow")).not.toBeNull();
    expect(screen.getByRole("button", { name: /save/i })).not.toBeNull();
    expect(screen.getByRole("tab", { name: /yaml/i })).not.toBeNull();
    expect(screen.queryByText(/Total Cost/i)).toBeNull();
    expect(screen.queryByRole("button", { name: /fork/i })).toBeNull();
  });

  it("keeps fork-draft mode on the shared topbar with editable workflow actions", async () => {
    const SharedTopbar = await loadSharedTopbarComponent();

    render(
      React.createElement(SharedTopbar, {
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
    const SharedTopbar = await loadSharedTopbarComponent();

    render(
      React.createElement(SharedTopbar, {
        mode: "historical",
        workflowName: "Research Workflow",
        run: buildRun("completed"),
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

  it("stops activating duplicate page-level legacy topbar paths in the workflow entry page", async () => {
    vi.doMock("react-router", () => ({
      useParams: () => ({ id: "wf-research" }),
      useBlocker: () => ({ state: "unblocked", proceed: vi.fn(), reset: vi.fn() }),
      useLocation: () => ({ state: undefined }),
    }));
    vi.doMock("@tanstack/react-query", () => ({
      useQueryClient: () => ({ invalidateQueries: vi.fn() }),
    }));
    vi.doMock("../CanvasTopbar", () => ({
      CanvasTopbar: () => React.createElement("div", null, "legacy-canvas-topbar"),
    }));
    vi.doMock("../WorkflowEditorSurface", () => ({
      WorkflowEditorSurface: ({ topbar }: { topbar?: React.ReactNode }) =>
        React.createElement("div", null, topbar),
    }));
    vi.doMock("../ForkDraftWorkflowSurface", () => ({
      ForkDraftWorkflowSurface: ({ topbar }: { topbar?: React.ReactNode }) =>
        React.createElement("div", null, topbar),
    }));
    vi.doMock("../CanvasStatusBar", () => ({ CanvasStatusBar: () => null }));
    vi.doMock("../CanvasBottomPanel", () => ({ CanvasBottomPanel: () => null }));
    vi.doMock("../FirstTimeTooltip", () => ({ FirstTimeTooltip: () => null }));
    vi.doMock("../PaletteSidebar", () => ({ PaletteSidebar: () => null }));
    vi.doMock("../WorkflowCanvas", () => ({ WorkflowCanvas: () => null }));
    vi.doMock("../YamlEditor", () => ({ YamlEditor: () => null }));
    vi.doMock("@/components/shared/PriorityBanner", () => ({ PriorityBanner: () => null }));
    vi.doMock("@/components/provider/ProviderModal", () => ({ ProviderModal: () => null }));
    vi.doMock("@/features/git/CommitDialog", () => ({ CommitDialog: () => null }));
    vi.doMock("@/api/git", () => ({ gitApi: { createSimBranch: vi.fn() } }));
    vi.doMock("../workflowSurfaceQueries", () => ({
      useWorkflow: () => ({ data: { commit_sha: "abc123" } }),
      useWorkflowRegressions: () => ({ data: { count: 0 } }),
    }));
    vi.doMock("@/queries/runs", () => ({
      useCreateRun: () => ({ mutate: vi.fn() }),
    }));
    vi.doMock("@/queries/settings", () => ({
      useProviders: () => ({ data: { items: [{ id: "provider-1", is_active: true }] } }),
    }));
    vi.doMock("@/queries/git", () => ({
      useGitStatus: () => ({ data: { is_clean: true, uncommitted_files: [] } }),
    }));
    vi.doMock("@/store/canvas", () => ({
      useCanvasStore: Object.assign(
        (selector: (state: {
          setActiveRunId: typeof vi.fn;
          blockCount: number;
          edgeCount: number;
          yamlContent: string;
          toPersistedState: () => undefined;
        }) => unknown) =>
          selector({
            setActiveRunId: vi.fn(),
            blockCount: 0,
            edgeCount: 0,
            yamlContent: "workflow:\n  name: Research Workflow\n",
            toPersistedState: () => undefined,
          }),
        {
          getState: () => ({
            setActiveRunId: vi.fn(),
            blockCount: 0,
            edgeCount: 0,
            yamlContent: "workflow:\n  name: Research Workflow\n",
            toPersistedState: () => undefined,
          }),
        },
      ),
    }));
    vi.doMock("@runsight/ui/dialog", () => ({
      Dialog: ({ children }: { children: React.ReactNode }) => React.createElement(React.Fragment, null, children),
      DialogContent: ({ children }: { children: React.ReactNode }) => React.createElement("div", null, children),
      DialogTitle: ({ children }: { children: React.ReactNode }) => React.createElement("div", null, children),
      DialogFooter: ({ children }: { children: React.ReactNode }) => React.createElement("div", null, children),
    }));
    vi.doMock("@runsight/ui/button", () => ({
      Button: ({ children }: { children: React.ReactNode }) => React.createElement("button", null, children),
    }));
    vi.doMock("@runsight/ui/empty-state", () => ({
      EmptyState: () => null,
    }));
    vi.doMock("lucide-react", () => ({
      Layout: () => React.createElement("span", null, "layout"),
    }));

    const { Component: CanvasPage } = await import("../CanvasPage");

    render(React.createElement(CanvasPage));

    expect(screen.queryByText("legacy-canvas-topbar")).toBeNull();
  });

  it("stops activating duplicate page-level legacy topbar paths in the historical run entry page", async () => {
    vi.doMock("react-router", () => ({
      useParams: () => ({ id: "run_123456" }),
    }));
    vi.doMock("@xyflow/react", () => ({
      ReactFlow: ({ children }: { children?: React.ReactNode }) => React.createElement("div", null, children),
      Background: () => null,
      Controls: () => null,
      MiniMap: () => null,
      ReactFlowProvider: ({ children }: { children: React.ReactNode }) => React.createElement(React.Fragment, null, children),
      useNodesState: () => [[], vi.fn(), vi.fn()],
      useEdgesState: () => [[], vi.fn(), vi.fn()],
    }));
    vi.doMock("@/queries/runs", () => ({
      useRun: () => ({
        data: buildRun("completed"),
        isLoading: false,
      }),
      useRunNodes: () => ({
        data: [],
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      }),
      useRunLogs: () => ({ data: { items: [] } }),
      useRunRegressions: () => ({ data: { items: [] } }),
    }));
    vi.doMock("@/components/shared/ErrorBoundary", () => ({
      CanvasErrorBoundary: ({ children }: { children: React.ReactNode }) => React.createElement(React.Fragment, null, children),
    }));
    vi.doMock("@runsight/ui/card", () => ({
      Card: ({ children }: { children: React.ReactNode }) => React.createElement("div", null, children),
    }));
    vi.doMock("@runsight/ui/button", () => ({
      Button: ({ children }: { children: React.ReactNode }) => React.createElement("button", null, children),
    }));
    vi.doMock("@/components/shared", () => ({
      PriorityBanner: () => null,
    }));
    vi.doMock("../RunCanvasNode", () => ({
      RunCanvasNode: () => null,
      CanvasNodeComponent: () => null,
      nodeTypes: {},
    }));
    vi.doMock("../RunInspectorPanel", () => ({
      RunInspectorPanel: () => null,
    }));
    vi.doMock("../RunBottomPanel", () => ({
      RunBottomPanel: () => null,
    }));
    vi.doMock("../../runs/RunDetailHeader", () => ({
      RunDetailHeader: () => React.createElement("div", null, "legacy-run-topbar"),
    }));
    vi.doMock("../../runs/HistoricalWorkflowSurface", () => ({
      HistoricalWorkflowSurface: ({ topbar }: { topbar?: React.ReactNode }) =>
        React.createElement("div", null, topbar),
    }));

    const { Component: RunDetail } = await import("../../runs/RunDetail");

    render(React.createElement(RunDetail));

    expect(screen.queryByText("legacy-run-topbar")).toBeNull();
  });
});
