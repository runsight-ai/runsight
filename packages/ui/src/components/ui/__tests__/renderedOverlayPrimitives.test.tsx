import * as React from "react";
import { ChevronDownIcon } from "lucide-react";
import { describe, expect, it, vi } from "vitest";

import { createUser, render, screen, waitFor, within } from "../../../test/testUtils";
import { Button } from "../button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "../command";
import {
  Dialog,
  DialogBody,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogOverlay,
  DialogPortal,
  DialogTitle,
  DialogTrigger,
} from "../dialog";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuPortal,
  DropdownMenuTrigger,
} from "../dropdown-menu";
import {
  Popover,
  PopoverContent,
  PopoverDescription,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from "../popover";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectScrollDownButton,
  SelectScrollUpButton,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from "../select";
import {
  Sheet,
  SheetBody,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "../sheet";
import { Toast } from "../toast";
import { SoulTip, Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "../tooltip";

function DialogHarness() {
  return (
    <Dialog>
      <DialogTrigger render={<Button variant="secondary">Open dialog</Button>} />
      <DialogContent size="lg">
        <DialogHeader>
          <DialogTitle>Workflow settings</DialogTitle>
          <DialogDescription>Choose how this workflow runs.</DialogDescription>
        </DialogHeader>
        <DialogBody>Dialog body copy</DialogBody>
        <DialogFooter showCloseButton>
          <DialogClose render={<Button variant="ghost" />}>Cancel</DialogClose>
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
        <SelectGroup>
          <SelectLabel>Hosted models</SelectLabel>
          <SelectItem value="gpt-5.4">GPT-5.4</SelectItem>
        </SelectGroup>
        <SelectSeparator />
        <SelectItem value="gpt-4o">GPT-4o</SelectItem>
      </SelectContent>
    </Select>
  );
}

function SelectScrollArrowHarness() {
  return (
    <Select open>
      <SelectTrigger>
        <SelectValue placeholder="Select a model" />
      </SelectTrigger>
      <SelectContent>
        <SelectScrollUpButton keepMounted className="manual-up-arrow" />
        <SelectItem value="gpt-5.4">GPT-5.4</SelectItem>
        <SelectScrollDownButton keepMounted className="manual-down-arrow" />
      </SelectContent>
    </Select>
  );
}

describe("rendered overlay primitive contracts", () => {
  it("renders command palette structure, filtering, separators, and shortcuts", async () => {
    const user = createUser();
    const onSelect = vi.fn();

    render(
      <Command>
        <CommandInput placeholder="Search actions" />
        <CommandList>
          <CommandEmpty>No actions found</CommandEmpty>
          <CommandGroup heading="Workflows">
            <CommandItem value="open workflow" onSelect={onSelect}>
              Open workflow
              <CommandShortcut>⌘O</CommandShortcut>
            </CommandItem>
            <CommandSeparator />
            <CommandItem value="delete workflow">Delete workflow</CommandItem>
          </CommandGroup>
        </CommandList>
      </Command>,
    );

    const input = screen.getByPlaceholderText("Search actions");
    const command = input.closest("[data-slot='command']");
    const item = screen.getByText("Open workflow").closest("[data-slot='command-item']");

    expect(command?.className).toContain("rounded-[var(--radius-2xl)]");
    expect(input.className).toContain("placeholder:text-(--text-muted)");
    expect(item).not.toBeNull();
    expect(screen.getByText("⌘O").className).toContain("font-mono");
    expect(document.querySelector("[data-slot='command-separator']")).not.toBeNull();

    await user.click(item as HTMLElement);

    expect(onSelect).toHaveBeenCalledTimes(1);
  });

  it("renders controlled popover content with header semantics and positioning props", async () => {
    render(
      <Popover open>
        <PopoverTrigger>Open filters</PopoverTrigger>
        <PopoverContent side="right" align="start" className="custom-popover">
          <PopoverHeader>
            <PopoverTitle>Run filters</PopoverTitle>
            <PopoverDescription>Narrow the run list.</PopoverDescription>
          </PopoverHeader>
        </PopoverContent>
      </Popover>,
    );

    await waitFor(() => {
      expect(document.body.querySelector("[data-slot='popover-content']")).not.toBeNull();
    });

    const content = document.body.querySelector("[data-slot='popover-content']");
    expect(content?.className).toContain("custom-popover");
    expect(content?.className).toContain("shadow-[var(--elevation-overlay-shadow)]");
    expect(screen.getByText("Run filters").closest("[data-slot='popover-title']")).not.toBeNull();
    expect(screen.getByText("Narrow the run list.").closest("[data-slot='popover-description']")).not.toBeNull();
  });

  it("renders sheet body, footer, side variant, and close affordance inside the portal", async () => {
    render(
      <Sheet open>
        <SheetTrigger>Open details</SheetTrigger>
        <SheetContent side="bottom">
          <SheetHeader>
            <SheetTitle>Run details</SheetTitle>
            <SheetDescription>Inspect the selected run.</SheetDescription>
          </SheetHeader>
          <SheetBody>Execution trace</SheetBody>
          <SheetFooter>
            <Button>Save</Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>,
    );

    await waitFor(() => {
      expect(document.body.querySelector("[data-slot='sheet-content']")).not.toBeNull();
    });

    const content = document.body.querySelector("[data-slot='sheet-content']");
    const overlay = document.body.querySelector("[data-slot='sheet-overlay']");

    expect(content?.getAttribute("data-side")).toBe("bottom");
    expect(content?.className).toContain("rounded-t-[var(--radius-xl)]");
    expect(overlay?.className).toContain("bg-black/50");
    expect(screen.getByText("Run details").closest("[data-slot='sheet-title']")).not.toBeNull();
    expect(screen.getByText("Execution trace").closest("[data-slot='sheet-body']")).not.toBeNull();
    expect(screen.getByRole("button", { name: "Close" })).toBeTruthy();
  });

  it("renders toast variants, ARIA roles, accent border, and dismiss actions", async () => {
    const user = createUser();
    const onDismiss = vi.fn();
    const { rerender } = render(
      <Toast
        variant="danger"
        title="Run failed"
        description="The evaluator rejected the output."
        onDismiss={onDismiss}
      />,
    );

    const alert = screen.getByRole("alert");
    expect(alert.getAttribute("data-variant")).toBe("danger");
    expect((alert as HTMLElement).style.borderLeft).toContain("var(--danger-9)");
    expect(screen.getByText("Run failed").className).toContain("text-heading");
    expect(screen.getByText("The evaluator rejected the output.").className).toContain("text-secondary");

    await user.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(onDismiss).toHaveBeenCalledTimes(1);

    rerender(<Toast variant="success" title="Saved" />);

    expect(screen.getByRole("status").getAttribute("data-variant")).toBe("success");
  });

  it("opens dialogs from the trigger and closes them from the built-in footer close affordance", async () => {
    const user = createUser();

    render(<DialogHarness />);

    expect(screen.queryByText("Workflow settings")).toBeNull();

    await user.click(screen.getByRole("button", { name: "Open dialog" }));

    const title = await screen.findByText("Workflow settings");
    const dialog = title.closest("[data-slot='dialog-content']");
    const overlay = document.body.querySelector("[data-slot='dialog-overlay']");
    const footer = screen.getByText("Save").closest("[data-slot='dialog-footer']");
    const closeButtons = screen.getAllByRole("button", { name: "Close" });
    expect(dialog?.className).toContain("w-(--overlay-width-lg)");
    expect(overlay).not.toBeNull();
    expect(screen.getByText("Choose how this workflow runs.")).toBeTruthy();
    expect(screen.getByText("Dialog body copy")).toBeTruthy();
    expect(closeButtons).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Cancel" })).toBeTruthy();
    expect(footer).not.toBeNull();

    await user.click(within(footer as HTMLElement).getByRole("button", { name: "Close" }));

    await waitFor(() => {
      expect(screen.queryByText("Workflow settings")).toBeNull();
    });
  });

  it("renders public portal and overlay exports inside their primitive roots", () => {
    render(
      <div>
        <Dialog open>
          <DialogPortal keepMounted data-testid="manual-dialog-portal">
            <DialogOverlay forceRender />
            <div>Manual dialog portal content</div>
          </DialogPortal>
        </Dialog>
        <DropdownMenu open>
          <DropdownMenuPortal keepMounted data-testid="manual-dropdown-portal">
            <div>Manual dropdown portal content</div>
          </DropdownMenuPortal>
        </DropdownMenu>
      </div>,
    );

    expect(screen.getByText("Manual dialog portal content")).toBeTruthy();
    expect(screen.getByText("Manual dropdown portal content")).toBeTruthy();
    expect(document.body.querySelector("[data-slot='dialog-overlay']")).not.toBeNull();
  });

  it("selects options through the rendered select trigger and popup", async () => {
    const user = createUser();
    const popupUser = createUser({ pointerEventsCheck: "never" });

    render(<SelectHarness />);

    const trigger = screen.getByText("Select a model").closest("[data-slot='select-trigger']");
    expect(trigger).not.toBeNull();
    expect(trigger?.className).toContain("border-(--border-default)");

    await user.click(trigger as Element);

    const popup = await screen.findByText("GPT-5.4");
    const content = popup.closest("[data-slot='select-content']");
    expect(content).not.toBeNull();
    expect(screen.getByText("Hosted models").closest("[data-slot='select-label']")).not.toBeNull();
    expect(content?.querySelector("[data-slot='select-group']")).not.toBeNull();
    expect(content?.querySelector("[data-slot='select-separator']")).not.toBeNull();

    const option = popup.closest("[data-slot='select-item']");
    expect(option).not.toBeNull();
    await popupUser.click(option as HTMLElement);

    await waitFor(() => {
      expect(screen.getByText("GPT-5.4")).toBeTruthy();
    });
    expect(screen.queryByText("Select a model")).toBeNull();
  });

  it("renders public select scroll arrow exports when kept mounted", async () => {
    render(<SelectScrollArrowHarness />);

    await waitFor(() => {
      expect(document.body.querySelector("[data-slot='select-scroll-up-button']")).not.toBeNull();
      expect(document.body.querySelector("[data-slot='select-scroll-down-button']")).not.toBeNull();
    });

    const scrollUp = document.body.querySelector("[data-slot='select-scroll-up-button']");
    const scrollDown = document.body.querySelector("[data-slot='select-scroll-down-button']");

    expect(scrollUp?.className).toContain("manual-up-arrow");
    expect(scrollUp?.getAttribute("aria-hidden")).toBe("true");
    expect(scrollDown?.className).toContain("manual-down-arrow");
    expect(scrollDown?.getAttribute("aria-hidden")).toBe("true");
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
          <DropdownMenuGroup>
            <DropdownMenuLabel>Workflow actions</DropdownMenuLabel>
            <DropdownMenuItem onClick={onRename}>Rename</DropdownMenuItem>
            <DropdownMenuCheckboxItem checked>Favorite</DropdownMenuCheckboxItem>
            <DropdownMenuRadioGroup value="canvas">
              <DropdownMenuRadioItem value="canvas">Canvas mode</DropdownMenuRadioItem>
            </DropdownMenuRadioGroup>
          </DropdownMenuGroup>
          <DropdownMenuSub>
            <DropdownMenuSubTrigger>More actions</DropdownMenuSubTrigger>
            <DropdownMenuSubContent>
              <DropdownMenuItem>Duplicate</DropdownMenuItem>
            </DropdownMenuSubContent>
          </DropdownMenuSub>
          <DropdownMenuItem variant="destructive">Delete</DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem>
            Open canvas
            <DropdownMenuShortcut>Cmd+K</DropdownMenuShortcut>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>,
    );

    await user.click(screen.getByRole("button", { name: /Actions/i }));

    const rename = await screen.findByText("Rename");
    const group = screen.getByText("Workflow actions").closest("[data-slot='dropdown-menu-group']");
    const checkboxItem = screen.getByText("Favorite").closest("[data-slot='dropdown-menu-checkbox-item']");
    const radioItem = screen.getByText("Canvas mode").closest("[data-slot='dropdown-menu-radio-item']");
    const subTrigger = screen.getByText("More actions").closest("[data-slot='dropdown-menu-sub-trigger']");
    const destructive = screen.getByText("Delete");
    const shortcutItem = screen.getByText("Open canvas").closest("[data-slot='dropdown-menu-item']");
    const separator = rename
      .closest("[data-slot='dropdown-menu-content']")
      ?.querySelector("[data-slot='dropdown-menu-separator']");

    expect(group).not.toBeNull();
    expect(checkboxItem?.querySelector("[data-slot='dropdown-menu-checkbox-item-indicator']")).not.toBeNull();
    expect(radioItem?.querySelector("[data-slot='dropdown-menu-radio-item-indicator']")).not.toBeNull();
    expect(subTrigger).not.toBeNull();
    expect(separator).not.toBeNull();
    expect(destructive.closest("[data-slot='dropdown-menu-item']")?.getAttribute("data-variant")).toBe("destructive");
    expect(screen.getByText("Cmd+K").className).toContain("font-mono");
    expect(shortcutItem).not.toBeNull();

    await user.hover(subTrigger as HTMLElement);
    expect(await screen.findByText("Duplicate")).toBeTruthy();

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
        <div>
          <Tooltip>
            <TooltipTrigger>Need help</TooltipTrigger>
            <TooltipContent side="right">Helpful copy</TooltipContent>
          </Tooltip>
          <SoulTip
            initial="W"
            color="hsl(220 70% 50%)"
            name="writer_main"
            model="gpt-5.4"
            provider="OpenAI"
            prompt="Draft a concise summary."
            rows={[{ key: "Role", val: "Writer" }]}
          />
        </div>
      </TooltipProvider>,
    );

    await user.hover(screen.getByRole("button", { name: "Need help" }));

    const content = await screen.findByText("Helpful copy");
    const popup = content.closest("[data-slot='tooltip-content']");

    expect(popup?.className).toContain("pointer-events-none");
    expect(screen.getByText("W")).toBeTruthy();
    expect(screen.getByText("writer_main")).toBeTruthy();
    expect(screen.getByText("OpenAI")).toBeTruthy();
    expect(screen.getByText("Writer")).toBeTruthy();

    await user.unhover(screen.getByRole("button", { name: "Need help" }));
    await waitFor(() => {
      expect(screen.queryByText("Helpful copy")).toBeNull();
    });
  });
});
