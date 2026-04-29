// @vitest-environment jsdom

import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@runsight/ui/stat-card", () => ({
  StatCard: ({
    label,
    value,
    variant,
    delta,
    deltaTone,
  }: {
    label: string;
    value: React.ReactNode;
    variant?: string;
    delta?: React.ReactNode;
    deltaTone?: string;
  }) =>
    React.createElement(
      "article",
      { "aria-label": label, "data-variant": variant ?? "default", "data-delta-tone": deltaTone ?? "" },
      [
        React.createElement("span", { key: "label" }, label),
        React.createElement("span", { key: "value", "data-testid": `${label}-value` }, value),
        delta ? React.createElement("span", { key: "delta" }, delta) : null,
      ],
    ),
}));

vi.mock("@runsight/ui/skeleton", () => ({
  Skeleton: () => React.createElement("div", { "data-testid": "dashboard-kpi-skeleton" }),
}));

import { DashboardKPIs } from "../components/DashboardKPIs";

afterEach(() => {
  cleanup();
});

describe("DashboardKPIs", () => {
  it("renders the four dashboard KPI cards with formatted values", () => {
    render(
      <DashboardKPIs
        isPending={false}
        isError={false}
        runsToday={7}
        runsYesterday={4}
        costTodayUsd={12.5}
        costYesterdayUsd={10}
        eval_pass_rate={0.86}
        evalPassYesterday={0.8}
        regressions={0}
        regressionsYesterday={2}
      />,
    );

    expect(screen.getByLabelText("Runs Today").textContent).toContain("7");
    expect(screen.getByLabelText("Eval Pass Rate").textContent).toContain("86%");
    expect(screen.getByLabelText("Cost Today").textContent).toContain("$12.50");
    expect(screen.getByTestId("Regressions-value").textContent).toBe("0");
    expect(screen.getByLabelText("Regressions").getAttribute("data-variant")).toBe("success");
  });

  it("uses warning states for lower eval pass rate and active regressions", () => {
    render(
      <DashboardKPIs
        isPending={false}
        isError={false}
        runsToday={3}
        runsYesterday={3}
        costTodayUsd={1}
        costYesterdayUsd={1}
        eval_pass_rate={0.68}
        evalPassYesterday={0.82}
        regressions={4}
        regressionsYesterday={1}
      />,
    );

    expect(screen.getByLabelText("Eval Pass Rate").getAttribute("data-variant")).toBe("warning");
    expect(screen.getByLabelText("Regressions").getAttribute("data-variant")).toBe("warning");
  });

  it("shows skeleton KPI shapes while loading and dashes while errored", () => {
    const { rerender } = render(
      <DashboardKPIs
        isPending
        isError={false}
        runsToday={0}
        runsYesterday={0}
        costTodayUsd={0}
        costYesterdayUsd={0}
        eval_pass_rate={null}
        evalPassYesterday={null}
        regressions={null}
        regressionsYesterday={null}
      />,
    );

    expect(screen.getAllByTestId("dashboard-kpi-skeleton")).toHaveLength(4);

    rerender(
      <DashboardKPIs
        isPending={false}
        isError
        runsToday="--"
        runsYesterday={0}
        costTodayUsd="--"
        costYesterdayUsd={0}
        eval_pass_rate={null}
        evalPassYesterday={null}
        regressions={null}
        regressionsYesterday={null}
      />,
    );

    expect(screen.getByTestId("Runs Today-value").textContent).toBe("--");
    expect(screen.getByTestId("Eval Pass Rate-value").textContent).toBe("\u2014");
    expect(screen.getByTestId("Cost Today-value").textContent).toBe("--");
    expect(screen.getByTestId("Regressions-value").textContent).toBe("\u2014");
  });
});
