// @vitest-environment jsdom

import type { WarningItem } from "@runsight/shared/zod";
import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const warningBadgeModulePath = "../warningBadge.utils";

async function loadWarningBadgeModule() {
  return import(warningBadgeModulePath);
}

vi.mock("lucide-react", () => ({
  Info: (props: Record<string, unknown>) =>
    React.createElement("svg", {
      ...props,
      "data-icon": "Info",
      "data-testid": "info-icon",
    }),
}));

const WARNING_SINGLE: WarningItem[] = [
  {
    message: "Tool definition warning",
    source: "tool_definitions",
    context: "lookup_profile",
  },
];

const WARNING_MULTI: WarningItem[] = [
  {
    message: "Tool definition warning",
    source: "tool_definitions",
    context: "lookup_profile",
  },
  {
    message: "Provider fallback warning",
    source: "providers",
    context: "openai",
  },
];

describe("RUN-843 warning badge utilities", () => {
  it("exports warning badge utilities and tooltip body component", async () => {
    const module = await loadWarningBadgeModule();

    expect(typeof module.shouldShowWarningBadge).toBe("function");
    expect(typeof module.formatWarningTooltip).toBe("function");
    expect(typeof module.WarningTooltipBody).toBe("function");
    expect(typeof module.WARNING_BADGE_CLASSES).toBe("string");
    expect(module.WARNING_BADGE_CLASSES).toContain("text-info-9");
    expect(module.WARNING_BADGE_CLASSES).toContain("inline-flex");
    expect(module.WARNING_BADGE_CLASSES).toContain("items-center");
    expect(module.WARNING_BADGE_CLASSES).toContain("gap-1");
  });

  it("shows warning badge only when at least one warning exists", async () => {
    const { shouldShowWarningBadge } = await loadWarningBadgeModule();

    expect(shouldShowWarningBadge(undefined)).toBe(false);
    expect(shouldShowWarningBadge([])).toBe(false);
    expect(shouldShowWarningBadge(WARNING_SINGLE)).toBe(true);
  });

  it("formats warning tooltip with warning count header and one line per warning", async () => {
    const { formatWarningTooltip } = await loadWarningBadgeModule();

    const single = formatWarningTooltip(WARNING_SINGLE);
    expect(single.header).toBe("1 warning");
    expect(single.lines).toHaveLength(1);
    expect(single.lines[0]).toContain("Tool definition warning");

    const multi = formatWarningTooltip(WARNING_MULTI);
    expect(multi.header).toBe("2 warnings");
    expect(multi.lines).toHaveLength(2);
    expect(multi.lines.join(" ")).toContain("Tool definition warning");
    expect(multi.lines.join(" ")).toContain("Provider fallback warning");
  });

  it("renders warning tooltip body with info icon semantics and warning lines", async () => {
    const module = await loadWarningBadgeModule();
    const WarningTooltipBody = module.WarningTooltipBody as React.ComponentType<{
      header: string;
      lines: string[];
    }>;

    render(
      <WarningTooltipBody
        header="2 warnings"
        lines={["Tool definition warning", "Provider fallback warning"]}
      />,
    );

    expect(screen.getByText("2 warnings")).toBeTruthy();
    expect(screen.getByText("Tool definition warning")).toBeTruthy();
    expect(screen.getByText("Provider fallback warning")).toBeTruthy();

    const infoIcon = screen.getByTestId("info-icon");
    expect(infoIcon).toHaveAttribute("aria-hidden", "true");
    expect(infoIcon.className).toContain("text-info-9");
  });
});
