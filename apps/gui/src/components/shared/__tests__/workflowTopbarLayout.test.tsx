// @vitest-environment jsdom

import React from "react";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { WorkflowTopbar } from "../WorkflowTopbar";

describe("WorkflowTopbar layout slots", () => {
  it("renders separate left, metrics, center, and actions slots in mock order", () => {
    const { container } = render(
      <WorkflowTopbar
        backTo="/runs"
        backLabel="Back to runs"
        title={<span>Research Pipeline</span>}
        metrics={<span>12.3s</span>}
        actions={<button type="button">Fork</button>}
        activeTab="canvas"
        onValueChange={() => undefined}
        toggleVisibility={{ canvas: true, yaml: true }}
      />,
    );

    const slotClassNames = Array.from(container.querySelector("header")?.children ?? []).map((child) =>
      child.className,
    );

    expect(container.querySelector(".topbar__left")).toBeTruthy();
    expect(container.querySelector(".topbar__metrics")).toBeTruthy();
    expect(container.querySelector(".topbar__center")).toBeTruthy();
    expect(container.querySelector(".topbar__actions")).toBeTruthy();
    expect(slotClassNames[0]).toContain("topbar__left");
    expect(slotClassNames[1]).toContain("topbar__metrics");
    expect(slotClassNames[2]).toContain("topbar__center");
    expect(slotClassNames[3]).toContain("topbar__actions");
    expect(screen.getByRole("button", { name: "Canvas" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Fork" })).toBeTruthy();
  });
});
