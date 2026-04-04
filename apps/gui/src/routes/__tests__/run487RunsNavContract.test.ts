// @vitest-environment jsdom

import React from "react";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { ShellLayout } from "../layouts/ShellLayout";

describe("RUN-487 sidebar runs navigation", () => {
  it("renders a first-class Runs nav item that links to /runs", async () => {
    const router = createMemoryRouter(
      [
        {
          path: "/",
          element: React.createElement(ShellLayout),
          children: [
            { index: true, element: React.createElement("div", null, "Home page") },
            { path: "runs", element: React.createElement("div", null, "Runs page") },
          ],
        },
      ],
      { initialEntries: ["/"] },
    );

    render(React.createElement(RouterProvider, { router }));

    const runsLink = screen.getByRole("link", { name: "Runs" });

    expect(runsLink.getAttribute("href")).toBe("/runs");
  });
});
