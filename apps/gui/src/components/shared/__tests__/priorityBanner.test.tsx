// @vitest-environment jsdom

import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("lucide-react", () => ({
  AlertTriangle: () => React.createElement("span", null),
  Info: () => React.createElement("span", null),
  X: () => React.createElement("span", null),
}));

import { PriorityBanner, type BannerCondition } from "../PriorityBanner";

function renderBanner(conditions: BannerCondition[]) {
  return render(<PriorityBanner conditions={conditions} />);
}

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  cleanup();
  localStorage.clear();
});

describe("PriorityBanner", () => {
  it("renders only the highest-priority active banner", () => {
    renderBanner([
      { type: "regressions", active: true, message: "Regression" },
      { type: "uncommitted", active: true, message: "Uncommitted" },
      { type: "explore", active: true, message: "Explore" },
    ]);

    expect(screen.getByRole("status").textContent).toContain("Explore");
    expect(screen.queryByText("Uncommitted")).toBeNull();
    expect(screen.queryByText("Regression")).toBeNull();
  });

  it("does not fall through to the next banner after dismissing the winner", () => {
    renderBanner([
      { type: "uncommitted", active: true, message: "Uncommitted" },
      { type: "regressions", active: true, message: "Regression" },
    ]);

    fireEvent.click(screen.getByLabelText("Dismiss banner"));

    expect(screen.queryByRole("status")).toBeNull();
  });

  it("persists explore dismissals in localStorage", () => {
    const conditions: BannerCondition[] = [
      { type: "explore", active: true, message: "Explore mode" },
    ];
    const view = renderBanner(conditions);

    fireEvent.click(screen.getByLabelText("Dismiss banner"));
    expect(localStorage.getItem("runsight:explore-banner-dismissed")).toBe("true");

    view.unmount();
    renderBanner(conditions);

    expect(screen.queryByRole("status")).toBeNull();
  });

  it("calls the active banner action", () => {
    const onClick = vi.fn();

    renderBanner([
      {
        type: "regressions",
        active: true,
        message: "Regressions found",
        action: { label: "Review", onClick },
      },
    ]);

    fireEvent.click(screen.getByText("Review"));

    expect(onClick).toHaveBeenCalledTimes(1);
  });
});
