import * as React from "react";
import { describe, expect, it } from "vitest";

import { createUser, render, screen, waitFor } from "../../../test/testUtils";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableMonoCell,
  TableRow,
} from "../table";
import { TabBadge, Tabs, TabsContent, TabsList, TabsTrigger } from "../tabs";

describe("rendered tabs and tables", () => {
  it("switches tabs through the rendered trigger and panel surface", async () => {
    const user = createUser();

    render(
      <Tabs defaultValue="overview">
        <TabsList variant="contained">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="runs">
            Runs <TabBadge>48</TabBadge>
          </TabsTrigger>
        </TabsList>
        <TabsContent value="overview">Overview content</TabsContent>
        <TabsContent value="runs">Runs content</TabsContent>
      </Tabs>,
    );

    const list = screen.getByRole("tablist");
    const overviewTab = screen.getByRole("tab", { name: "Overview" });
    const runsTab = screen.getByRole("tab", { name: /Runs 48/ });

    expect(list.className).toContain("bg-surface-tertiary");
    expect(overviewTab.getAttribute("aria-selected")).toBe("true");
    expect(screen.getByText("Overview content")).toBeTruthy();
    expect(screen.getByText("48").className).toContain("font-mono");

    await user.click(runsTab);

    await waitFor(() => {
      expect(runsTab.getAttribute("aria-selected")).toBe("true");
    });
    expect(screen.queryByText("Overview content")).toBeNull();
    expect(screen.getByText("Runs content")).toBeTruthy();
  });

  it("renders table wrappers, sortable headers, and monospace data cells", () => {
    const { container } = render(
      <Table>
        <TableCaption>Recent runs</TableCaption>
        <TableHeader>
          <tr>
            <TableHead aria-sort="ascending">Status</TableHead>
            <TableHead>Run ID</TableHead>
          </tr>
        </TableHeader>
        <TableBody>
          <TableRow aria-selected="true">
            <TableCell>Completed</TableCell>
            <TableMonoCell>run_display_primary</TableMonoCell>
          </TableRow>
        </TableBody>
        <TableFooter>
          <TableRow>
            <TableCell>Total</TableCell>
            <TableCell>1 run</TableCell>
          </TableRow>
        </TableFooter>
      </Table>,
    );

    const wrapper = container.querySelector("[data-slot='table-container']");
    const header = screen.getByRole("columnheader", { name: "Status" });
    const row = screen.getByRole("row", { name: /Completed run_display_primary/ });
    const monoCell = screen.getByText("run_display_primary");

    expect(wrapper?.className).toContain("overflow-x-auto");
    expect(header.getAttribute("aria-sort")).toBe("ascending");
    expect(header.className).toContain("font-mono");
    expect(row.getAttribute("aria-selected")).toBe("true");
    expect(monoCell.className).toContain("font-mono");
    expect(screen.getByText("Recent runs").tagName).toBe("CAPTION");
    expect(screen.getByText("Total").closest("tfoot")).not.toBeNull();
  });
});
