// @vitest-environment jsdom

import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const mocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
}));

vi.mock("../../../api/client", () => ({
  api: {
    get: mocks.apiGet,
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock("@tanstack/react-query", () => ({
  useQuery: (options: Record<string, unknown>) => options,
  useMutation: vi.fn(),
  useQueryClient: vi.fn(),
}));

const RUN_DETAIL_SOURCE = readFileSync(resolve(__dirname, "../RunDetail.tsx"), "utf-8");

beforeEach(() => {
  vi.resetModules();
  mocks.apiGet.mockReset();
  cleanup();
});

describe("run-node adapter contract failures (RUN-498)", () => {
  it("rejects a non-array run-node payload instead of silently returning an empty graph", async () => {
    mocks.apiGet.mockResolvedValue({
      items: [],
    });

    const { runsApi } = await import("../../../api/runs");

    await expect(
      (runsApi as { getRunNodes: (id: string) => Promise<unknown> }).getRunNodes("run_1"),
    ).rejects.toThrow(/run.*node.*(contract|response)/i);
  });

  it("preserves backend failures distinctly from run-node contract failures", async () => {
    mocks.apiGet.mockRejectedValue(new Error("Nodes request failed"));

    const { runsApi } = await import("../../../api/runs");

    await expect(
      (runsApi as { getRunNodes: (id: string) => Promise<unknown> }).getRunNodes("run_1"),
    ).rejects.toThrow("Nodes request failed");
  });

  it("propagates malformed run-node payloads through useRunNodes as errors", async () => {
    mocks.apiGet.mockResolvedValue({
      items: [],
    });

    const { useRunNodes } = await import("../../../queries/runs");

    const query = (useRunNodes as unknown as (id: string) => { queryFn: () => Promise<unknown> })(
      "run_1",
    );

    await expect(query.queryFn()).rejects.toThrow(/run.*node.*(contract|response)/i);
  });
});

describe("RunDetail contract-failure UI (RUN-498)", () => {
  it("reads explicit node-loading error state from useRunNodes instead of treating missing nodes as a blank graph", () => {
    expect(
      RUN_DETAIL_SOURCE,
      "Expected RunDetail to read an explicit error state from useRunNodes",
    ).toMatch(
      /const\s*\{\s*[^}]*\b(?:isError|error|refetch)\b[^}]*\}\s*=\s*useRunNodes\s*\(/,
    );
  });

  it("renders a deliberate run-graph error state with retry guidance when node parsing fails", () => {
    const hasRunGraphErrorCopy =
      /run graph|load run graph|unable to load/i.test(RUN_DETAIL_SOURCE);
    const hasRetryGuidance = /retry|try again|refetch/i.test(RUN_DETAIL_SOURCE);

    expect(
      hasRunGraphErrorCopy && hasRetryGuidance,
      "Expected RunDetail to render visible run-graph error copy with retry guidance for contract failures",
    ).toBe(true);
  });

  it("renders a visible run-graph contract failure state instead of the canvas when useRunNodes errors", async () => {
    vi.doMock("react-router", () => ({
      useParams: () => ({ id: "run_1" }),
    }));

    vi.doMock("@xyflow/react", () => ({
      ReactFlowProvider: ({ children }: { children: React.ReactNode }) =>
        React.createElement(React.Fragment, null, children),
      ReactFlow: () => React.createElement("div", null, "React flow canvas"),
      Background: () => null,
      Controls: () => null,
      MiniMap: () => null,
      useNodesState: () => [[], vi.fn(), vi.fn()],
      useEdgesState: () => [[], vi.fn(), vi.fn()],
    }));

    vi.doMock("@/queries/runs", () => ({
      useRun: () => ({
        data: {
          id: "run_1",
          workflow_id: "wf_1",
          workflow_name: "Test workflow",
          status: "completed",
          started_at: null,
          completed_at: null,
          duration_seconds: null,
          total_cost_usd: 0,
          total_tokens: 0,
        },
        isLoading: false,
      }),
      useRunNodes: () => ({
        data: undefined,
        isLoading: false,
        isError: true,
        error: new Error("Run node response contract invalid"),
        refetch: vi.fn(),
      }),
      useRunLogs: () => ({
        data: { items: [] },
      }),
    }));

    vi.doMock("@/queries/dashboard", () => ({
      useAttentionItems: () => ({
        data: { items: [] },
      }),
    }));

    vi.doMock("@/components/shared/ErrorBoundary", () => ({
      CanvasErrorBoundary: ({ children }: { children: React.ReactNode }) =>
        React.createElement(React.Fragment, null, children),
    }));

    vi.doMock("../RunCanvasNode", () => ({
      RunCanvasNode: () => null,
      CanvasNodeComponent: () => null,
      nodeTypes: {},
    }));

    vi.doMock("../RunInspectorPanel", () => ({
      RunInspectorPanel: () => React.createElement("div", null, "Inspector"),
    }));

    vi.doMock("../RunBottomPanel", () => ({
      RunBottomPanel: () => React.createElement("div", null, "Bottom panel"),
    }));

    vi.doMock("../RunDetailHeader", () => ({
      RunDetailHeader: () => React.createElement("div", null, "Header"),
    }));

    vi.doMock("../runDetailUtils", () => ({
      getIconForBlockType: () => "icon",
      mapRunStatus: (status: string) => status,
    }));

    vi.doMock("@runsight/ui/card", () => ({
      Card: ({ children }: { children: React.ReactNode }) =>
        React.createElement("div", null, children),
    }));

    vi.doMock("@runsight/ui/badge", () => ({
      Badge: ({ children }: { children: React.ReactNode }) =>
        React.createElement("span", null, children),
    }));

    vi.doMock("lucide-react", () => ({
      AlertTriangle: () => null,
      Activity: () => null,
    }));

    const { Component } = await import("../RunDetail");

    render(React.createElement(Component));

    expect(await screen.findByText(/unable to load run graph/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: /retry/i })).toBeTruthy();
    expect(screen.queryByText("React flow canvas")).toBeNull();
  });
});
