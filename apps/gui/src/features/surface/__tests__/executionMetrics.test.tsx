// @vitest-environment jsdom

import React from "react";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const harness = vi.hoisted(() => ({
  activeRunId: null as string | null,
  run: null as null | {
    id: string;
    status: "completed" | "failed" | "running";
    total_cost_usd: number;
    total_tokens: number;
    duration_seconds: number | null;
  },
}));

vi.mock("@/queries/runs", () => ({
  useRun: () => ({ data: harness.run }),
}));

vi.mock("@/store/canvas", () => ({
  useCanvasStore: (selector: (state: { activeRunId: string | null }) => unknown) =>
    selector({ activeRunId: harness.activeRunId }),
}));

vi.mock("lucide-react", () => ({
  AlertCircle: () => React.createElement("span", { "data-testid": "failed-icon" }),
  CheckCircle: () => React.createElement("span", { "data-testid": "completed-icon" }),
  Clock: () => React.createElement("span", null),
  Coins: () => React.createElement("span", null),
  Hash: () => React.createElement("span", null),
}));

import { ExecutionMetrics } from "../ExecutionMetrics";

beforeEach(() => {
  harness.activeRunId = null;
  harness.run = null;
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("ExecutionMetrics", () => {
  it("renders completed run cost, tokens, and duration", async () => {
    harness.run = {
      id: "run_completed",
      status: "completed",
      total_cost_usd: 1.2345,
      total_tokens: 2500,
      duration_seconds: 75,
    };

    render(<ExecutionMetrics runId="run_completed" />);

    const status = await screen.findByRole("status");
    expect(status.getAttribute("aria-label")).toContain("Run completed");
    expect(status.textContent).toContain("$1.2345");
    expect(status.textContent).toContain("2.5k tokens");
    expect(status.textContent).toContain("1m 15s");
    expect(screen.getByTestId("completed-icon")).toBeTruthy();
  });

  it("renders failed run metrics with the failed status", async () => {
    harness.run = {
      id: "run_failed",
      status: "failed",
      total_cost_usd: 0.5,
      total_tokens: 42,
      duration_seconds: null,
    };

    render(<ExecutionMetrics runId="run_failed" />);

    const status = await screen.findByRole("status");
    expect(status.getAttribute("aria-label")).toContain("Run failed");
    expect(status.textContent).toContain("$0.5000");
    expect(status.textContent).toContain("42 tokens");
    expect(status.textContent).toContain("--");
    expect(screen.getByTestId("failed-icon")).toBeTruthy();
  });

  it("auto-hides terminal metrics after five seconds", async () => {
    vi.useFakeTimers();
    harness.run = {
      id: "run_hidden",
      status: "completed",
      total_cost_usd: 0.1,
      total_tokens: 10,
      duration_seconds: 2,
    };

    render(<ExecutionMetrics runId="run_hidden" />);
    await act(async () => undefined);
    expect(screen.getByRole("status")).toBeTruthy();

    act(() => {
      vi.advanceTimersByTime(5000);
    });

    expect(screen.queryByRole("status")).toBeNull();
  });

  it("hides terminal metrics when a new run becomes active", async () => {
    harness.run = {
      id: "run_previous",
      status: "completed",
      total_cost_usd: 0.1,
      total_tokens: 10,
      duration_seconds: 2,
    };

    const { rerender } = render(<ExecutionMetrics runId="run_previous" />);
    expect(await screen.findByRole("status")).toBeTruthy();

    harness.activeRunId = "run_next";
    rerender(<ExecutionMetrics runId="run_previous" />);

    await waitFor(() => {
      expect(screen.queryByRole("status")).toBeNull();
    });
  });
});
