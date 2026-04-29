// @vitest-environment jsdom

import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const harness = vi.hoisted(() => ({
  status: undefined as
    | undefined
    | {
        is_clean: boolean;
        uncommitted_files: Array<{ path: string; status: string }>;
      },
  dialogProps: [] as Array<Record<string, unknown>>,
}));

vi.mock("@/queries/git", () => ({
  useGitStatus: () => ({ data: harness.status }),
}));

vi.mock("../CommitDialog", () => ({
  CommitDialog: (props: Record<string, unknown>) => {
    harness.dialogProps.push(props);
    return props.open
      ? React.createElement("div", { "data-testid": "commit-dialog" }, "Commit Changes")
      : null;
  },
}));

import { GitBadge } from "../GitBadge";

beforeEach(() => {
  harness.status = undefined;
  harness.dialogProps = [];
});

afterEach(() => {
  cleanup();
});

describe("GitBadge", () => {
  it("stays hidden while git status is unavailable or clean", () => {
    const { rerender } = render(<GitBadge />);
    expect(screen.queryByRole("button")).toBeNull();

    harness.status = { is_clean: true, uncommitted_files: [] };
    rerender(<GitBadge />);

    expect(screen.queryByRole("button")).toBeNull();
  });

  it("shows uncommitted file count and opens the commit dialog", async () => {
    const files = [
      { path: "custom/workflows/demo.yaml", status: "modified" },
      { path: "custom/souls/reviewer.yaml", status: "added" },
    ];
    harness.status = { is_clean: false, uncommitted_files: files };

    render(<GitBadge />);

    const badge = screen.getByRole("button", { name: "2 uncommitted changes" });
    expect(badge.textContent).toContain("2 uncommitted");
    expect(harness.dialogProps.at(-1)).toMatchObject({
      open: false,
      files,
    });

    await userEvent.click(badge);

    expect(screen.getByTestId("commit-dialog")).toBeTruthy();
    expect(harness.dialogProps.at(-1)).toMatchObject({
      open: true,
      files,
    });
  });
});
