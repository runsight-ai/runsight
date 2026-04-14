import type { WarningItem } from "@runsight/shared/zod";
import { describe, expect, it } from "vitest";

const warningBadgeModulePath = "../warningBadge.utils";

async function loadWarningBadgeModule() {
  return import(warningBadgeModulePath);
}

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
  it("exports shouldShowWarningBadge, formatWarningTooltip, and WARNING_BADGE_CLASSES", async () => {
    const module = await loadWarningBadgeModule();

    expect(typeof module.shouldShowWarningBadge).toBe("function");
    expect(typeof module.formatWarningTooltip).toBe("function");
    expect(module.WARNING_BADGE_CLASSES).toBe(
      "text-[var(--info-11)] font-medium text-xs inline-flex items-center gap-1",
    );
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
});
