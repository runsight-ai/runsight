// @vitest-environment jsdom

import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ConnectionFeedback } from "../components/ConnectionFeedback";

describe("ConnectionFeedback accessibility", () => {
  it("does not announce anything while idle", () => {
    render(<ConnectionFeedback status="idle" message="" modelCount={0} />);

    expect(screen.queryByRole("status")).toBeNull();
  });

  it("announces connection testing in a polite status region", () => {
    render(<ConnectionFeedback status="testing" message="" modelCount={0} />);

    const status = screen.getByRole("status");

    expect(status).toHaveAttribute("aria-live", "polite");
    expect(status).toHaveTextContent("Testing connection...");
  });

  it("announces successful connections with the available model count", () => {
    render(<ConnectionFeedback status="success" message="" modelCount={3} />);

    const status = screen.getByRole("status");

    expect(status).toHaveAttribute("aria-live", "polite");
    expect(status).toHaveTextContent(/Connected.*3 models available/);
  });

  it("announces custom and default connection errors", () => {
    const { rerender } = render(
      <ConnectionFeedback status="error" message="Key expired" modelCount={0} />,
    );

    let status = screen.getByRole("status");

    expect(status).toHaveAttribute("aria-live", "polite");
    expect(status).toHaveTextContent("Key expired");

    rerender(<ConnectionFeedback status="error" message="" modelCount={0} />);

    status = screen.getByRole("status");
    expect(status).toHaveTextContent(/Invalid key/);
  });
});
