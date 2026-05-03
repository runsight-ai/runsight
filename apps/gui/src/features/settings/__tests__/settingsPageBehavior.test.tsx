// @vitest-environment jsdom

import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

vi.mock("../ProvidersTab", () => ({
  ProvidersTab: ({
    dialogOpen,
    editing,
  }: {
    dialogOpen: boolean;
    editing?: unknown;
  }) => (
    <section aria-label="Provider settings">
      <p>Provider management content</p>
      {dialogOpen ? (
        <div role="dialog" aria-label={editing ? "Edit provider" : "Add provider"}>
          Provider dialog open
        </div>
      ) : null}
    </section>
  ),
}));

vi.mock("../ModelsTab", () => ({
  ModelsTab: () => (
    <section aria-label="Fallback settings">
      <p>Fallback management content</p>
    </section>
  ),
}));

import { Component as SettingsPage } from "../SettingsPage";

describe("Settings page rendered tabs", () => {
  it("renders the settings tab set with only Providers and Fallback sections", () => {
    render(<SettingsPage />);

    expect(screen.getByRole("heading", { name: "Settings" })).toBeTruthy();
    expect(screen.getByRole("tablist", { name: "Settings sections" })).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Providers" })).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Fallback" })).toBeTruthy();
    expect(screen.queryByRole("tab", { name: /default model/i })).toBeNull();
    expect(screen.queryByRole("tab", { name: "Models" })).toBeNull();
  });

  it("shows provider actions only on the Providers tab and opens the add dialog from the header", async () => {
    const user = userEvent.setup();

    render(<SettingsPage />);

    expect(screen.getByText("Provider management content")).toBeTruthy();
    const addProvider = screen.getByRole("button", { name: "Add Provider" });

    await user.click(addProvider);

    expect(screen.getByRole("dialog", { name: "Add provider" })).toBeTruthy();

    await user.click(screen.getByRole("tab", { name: "Fallback" }));

    await waitFor(() => {
      expect(screen.getByText("Fallback management content")).toBeTruthy();
    });
    expect(screen.queryByRole("button", { name: "Add Provider" })).toBeNull();
  });

  it("does not activate another settings tab from focus alone", async () => {
    const user = userEvent.setup();

    render(<SettingsPage />);

    const providersTab = screen.getByRole("tab", { name: "Providers" });
    const fallbackTab = screen.getByRole("tab", { name: "Fallback" });

    expect(providersTab.getAttribute("aria-selected")).toBe("true");

    fallbackTab.focus();

    expect(providersTab.getAttribute("aria-selected")).toBe("true");
    expect(screen.getByText("Provider management content")).toBeTruthy();

    await user.keyboard("{Enter}");

    await waitFor(() => {
      expect(fallbackTab.getAttribute("aria-selected")).toBe("true");
    });
    expect(screen.getByText("Fallback management content")).toBeTruthy();
  });
});
