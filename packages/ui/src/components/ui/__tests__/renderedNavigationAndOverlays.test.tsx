import * as React from "react";
import { ChevronDownIcon } from "lucide-react";
import { describe, expect, it, vi } from "vitest";

import { createUser, render, screen, waitFor, within } from "../../../test/testUtils";
import { Button } from "../button";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuTrigger,
} from "../dropdown-menu";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../select";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableMonoCell,
  TableRow,
} from "../table";
import { TabBadge, Tabs, TabsContent, TabsList, TabsTrigger } from "../tabs";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "../tooltip";

function DialogHarness() {
  return (
    <Dialog>
      <DialogTrigger render={<Button variant="secondary">Open dialog</Button>} />
      <DialogContent size="lg">
        <DialogHeader>
          <DialogTitle>Workflow settings</DialogTitle>
        </DialogHeader>
        <DialogBody>Dialog body copy</DialogBody>
        <DialogFooter showCloseButton>
          <Button>Save</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function SelectHarness() {
  return (
    <Select>
      <SelectTrigger>
        <SelectValue placeholder="Select a model" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="gpt-5.4">GPT-5.4</SelectItem>
        <SelectItem value="gpt-4o">GPT-4o</SelectItem>
      </SelectContent>
    </Select>
  );
}

describe("rendered navigation and overlay contracts", () => {
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
            <TableMonoCell>run_123</TableMonoCell>
          </TableRow>
        </TableBody>
      </Table>,
    );

    const wrapper = container.querySelector("[data-slot='table-container']");
    const header = screen.getByRole("columnheader", { name: "Status" });
    const row = screen.getByRole("row", { name: /Completed run_123/ });
    const monoCell = screen.getByText("run_123");

    expect(wrapper?.className).toContain("overflow-x-auto");
    expect(header.getAttribute("aria-sort")).toBe("ascending");
    expect(header.className).toContain("font-mono");
    expect(row.getAttribute("aria-selected")).toBe("true");
    expect(monoCell.className).toContain("font-mono");
    expect(screen.getByText("Recent runs").tagName).toBe("CAPTION");
  });

  it("opens dialogs from the trigger and closes them from the built-in footer close affordance", async () => {
    const user = createUser();

    render(<DialogHarness />);

    expect(screen.queryByText("Workflow settings")).toBeNull();

    await user.click(screen.getByRole("button", { name: "Open dialog" }));

    const title = await screen.findByText("Workflow settings");
    const dialog = title.closest("[data-slot='dialog-content']");
    const footer = screen.getByText("Save").closest("[data-slot='dialog-footer']");
    const closeButtons = screen.getAllByRole("button", { name: "Close" });
    expect(dialog?.className).toContain("w-(--overlay-width-lg)");
    expect(screen.getByText("Dialog body copy")).toBeTruthy();
    expect(closeButtons).toHaveLength(2);
    expect(footer).not.toBeNull();

    await user.click(within(footer as HTMLElement).getByRole("button", { name: "Close" }));

    await waitFor(() => {
      expect(screen.queryByText("Workflow settings")).toBeNull();
    });
  });

  it("selects options through the rendered select trigger and popup", async () => {
    const user = createUser();

    render(<SelectHarness />);

    const trigger = screen.getByText("Select a model").closest("[data-slot='select-trigger']");
    expect(trigger).not.toBeNull();
    expect(trigger?.className).toContain("border-(--border-default)");

    await user.click(trigger as Element);

    const popup = await screen.findByText("GPT-5.4");
    expect(popup.closest("[data-slot='select-content']")).not.toBeNull();

    await user.click(screen.getByText("GPT-5.4"));

    await waitFor(() => {
      expect(screen.getByText("GPT-5.4")).toBeTruthy();
    });
    expect(screen.queryByText("Select a model")).toBeNull();
  });

  it("opens dropdown menus, preserves separator/shortcut structure, and invokes clicked items", async () => {
    const user = createUser();
    const onRename = vi.fn();

    render(
      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button variant="secondary" size="sm">
              Actions <ChevronDownIcon />
            </Button>
          }
        />
        <DropdownMenuContent>
          <DropdownMenuItem onClick={onRename}>Rename</DropdownMenuItem>
          <DropdownMenuItem variant="destructive">Delete</DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem>
            Open canvas
            <DropdownMenuShortcut>⌘K</DropdownMenuShortcut>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>,
    );

    await user.click(screen.getByRole("button", { name: /Actions/i }));

    const rename = await screen.findByText("Rename");
    const destructive = screen.getByText("Delete");
    const shortcutItem = screen.getByText("Open canvas").closest("[data-slot='dropdown-menu-item']");
    const separator = rename
      .closest("[data-slot='dropdown-menu-content']")
      ?.querySelector("[data-slot='dropdown-menu-separator']");

    expect(separator).not.toBeNull();
    expect(destructive.closest("[data-slot='dropdown-menu-item']")?.getAttribute("data-variant")).toBe("destructive");
    expect(screen.getByText("⌘K").className).toContain("font-mono");
    expect(shortcutItem).not.toBeNull();

    await user.click(rename);

    expect(onRename).toHaveBeenCalledTimes(1);
    await waitFor(() => {
      expect(screen.queryByText("Rename")).toBeNull();
    });
  });

  it("shows tooltip content on hover and keeps the popup non-interactive", async () => {
    const user = createUser();

    render(
      <TooltipProvider delay={0}>
        <Tooltip>
          <TooltipTrigger>Need help</TooltipTrigger>
          <TooltipContent side="right">Helpful copy</TooltipContent>
        </Tooltip>
      </TooltipProvider>,
    );

    await user.hover(screen.getByRole("button", { name: "Need help" }));

    const content = await screen.findByText("Helpful copy");
    const popup = content.closest("[data-slot='tooltip-content']");

    expect(popup?.className).toContain("pointer-events-none");

    await user.unhover(screen.getByRole("button", { name: "Need help" }));
    await waitFor(() => {
      expect(screen.queryByText("Helpful copy")).toBeNull();
    });
  });
});
