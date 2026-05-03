// @vitest-environment jsdom

import React from "react";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { ShellLayout } from "../layouts/ShellLayout";

describe("sidebar runs navigation", () => {
  it("renders first-class Flows and Runs nav items", async () => {
    const router = createMemoryRouter(
      [
        {
          path: "/",
          element: React.createElement(ShellLayout),
          children: [
            { index: true, element: React.createElement("div", null, "Home page") },
            { path: "flows", element: React.createElement("div", null, "Flows page") },
            { path: "runs", element: React.createElement("div", null, "Runs page") },
          ],
        },
      ],
      { initialEntries: ["/"] },
    );

    render(React.createElement(RouterProvider, { router }));

    const flowsLink = screen.getByRole("link", { name: "Flows" });
    const runsLink = screen.getByRole("link", { name: "Runs" });

    expect(flowsLink.getAttribute("href")).toBe("/flows");
    expect(runsLink.getAttribute("href")).toBe("/runs");
  });
});
