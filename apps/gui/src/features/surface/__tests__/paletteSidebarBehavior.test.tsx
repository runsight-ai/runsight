// @vitest-environment jsdom

import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const harness = vi.hoisted(() => ({
  souls: [
    { id: "soul_reviewer", role: "Reviewer" },
    { id: "soul_planner", role: "Planner" },
  ],
}));

vi.mock("@/queries/souls", () => ({
  useSouls: () => ({
    data: { items: harness.souls, total: harness.souls.length },
  }),
}));

vi.mock("@runsight/ui/tooltip", () => ({
  TooltipProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipTrigger: ({
    children,
    className,
    draggable,
    onDragStart,
  }: {
    children?: React.ReactNode;
    className?: string;
    draggable?: boolean;
    onDragStart?: React.DragEventHandler<HTMLElement>;
  }) => (
    <button
      type="button"
      className={className}
      draggable={draggable}
      onDragStart={onDragStart}
    >
      {children}
    </button>
  ),
  TooltipContent: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}));

vi.mock("lucide-react", () => ({
  ArrowRightLeft: () => <span aria-hidden="true" />,
  GitFork: () => <span aria-hidden="true" />,
  Code: () => <span aria-hidden="true" />,
  ChevronLeft: () => <span aria-hidden="true" />,
  User: () => <span aria-hidden="true" />,
}));

import { PaletteSidebar } from "../PaletteSidebar";

function renderPalette(onCollapse = vi.fn()) {
  render(<PaletteSidebar onCollapse={onCollapse} />);
  return { onCollapse };
}

function makeDataTransfer() {
  const data = new Map<string, string>();
  return {
    effectAllowed: "none",
    setData: vi.fn((type: string, value: string) => {
      data.set(type, value);
    }),
    getData: (type: string) => data.get(type) ?? "",
  };
}

beforeEach(() => {
  harness.souls = [
    { id: "soul_reviewer", role: "Reviewer" },
    { id: "soul_planner", role: "Planner" },
  ];
});

afterEach(() => {
  cleanup();
});

describe("PaletteSidebar visible items", () => {
  it("shows supported block types and loaded souls without retired block labels", () => {
    renderPalette();

    expect(screen.getByText("Linear")).toBeTruthy();
    expect(screen.getByText("Gate")).toBeTruthy();
    expect(screen.getByText("Code")).toBeTruthy();
    expect(screen.getByText("Reviewer")).toBeTruthy();
    expect(screen.getByText("Planner")).toBeTruthy();
    expect(screen.queryByText("FileWriter")).toBeNull();
  });
});

describe("PaletteSidebar search", () => {
  it("filters block and soul items case-insensitively", async () => {
    const user = userEvent.setup();
    renderPalette();

    await user.type(screen.getByPlaceholderText("Search blocks..."), "ga");

    expect(screen.getByText("Gate")).toBeTruthy();
    expect(screen.queryByText("Linear")).toBeNull();
    expect(screen.queryByText("Reviewer")).toBeNull();

    await user.clear(screen.getByPlaceholderText("Search blocks..."));
    await user.type(screen.getByPlaceholderText("Search blocks..."), "review");

    expect(screen.getByText("Reviewer")).toBeTruthy();
    expect(screen.queryByText("Planner")).toBeNull();
    expect(screen.queryByText("Gate")).toBeNull();
  });

  it("clears search and hides the input when the sidebar collapses", async () => {
    const user = userEvent.setup();
    const { onCollapse } = renderPalette();

    await user.type(screen.getByPlaceholderText("Search blocks..."), "gate");
    expect(screen.queryByText("Linear")).toBeNull();

    await user.click(screen.getByRole("button", { name: /collapse sidebar/i }));

    expect(onCollapse).toHaveBeenCalledWith(true);
    expect(screen.queryByPlaceholderText("Search blocks...")).toBeNull();

    await user.click(screen.getByRole("button", { name: /expand sidebar/i }));

    expect(screen.getByPlaceholderText("Search blocks...")).toHaveValue("");
    expect(screen.getByText("Linear")).toBeTruthy();
  });
});

describe("PaletteSidebar drag payloads", () => {
  it("sets a block drag payload with copy semantics", () => {
    renderPalette();
    const dataTransfer = makeDataTransfer();

    fireEvent.dragStart(screen.getByText("Linear").closest("div")!, { dataTransfer });

    expect(dataTransfer.effectAllowed).toBe("copy");
    expect(dataTransfer.setData).toHaveBeenCalledWith(
      "application/runsight-block",
      JSON.stringify({ type: "block", label: "Linear" }),
    );
  });

  it("sets a soul drag payload with copy semantics", () => {
    renderPalette();
    const dataTransfer = makeDataTransfer();

    fireEvent.dragStart(screen.getByText("Reviewer").closest("div")!, { dataTransfer });

    expect(dataTransfer.effectAllowed).toBe("copy");
    expect(dataTransfer.setData).toHaveBeenCalledWith(
      "application/runsight-soul",
      JSON.stringify({ type: "soul", label: "Reviewer" }),
    );
  });
});
