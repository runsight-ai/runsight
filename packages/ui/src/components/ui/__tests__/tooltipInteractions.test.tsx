import { describe, expect, it } from "vitest";

import { createUser, render, screen, waitFor } from "../../../test/testUtils";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "../tooltip";

describe("Tooltip interactions", () => {
  it("opens on hover and closes on unhover", async () => {
    const user = createUser();

    render(
      <TooltipProvider delay={0}>
        <Tooltip>
          <TooltipTrigger>Hover target</TooltipTrigger>
          <TooltipContent>Helpful copy</TooltipContent>
        </Tooltip>
      </TooltipProvider>,
    );

    const trigger = screen.getByRole("button", { name: "Hover target" });

    expect(screen.queryByText("Helpful copy")).toBeNull();

    await user.hover(trigger);

    expect(await screen.findByText("Helpful copy")).toBeTruthy();

    await user.unhover(trigger);

    await waitFor(() => {
      expect(screen.queryByText("Helpful copy")).toBeNull();
    });
  });
});
