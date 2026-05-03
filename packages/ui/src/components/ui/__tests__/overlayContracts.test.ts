/**
 * Governance: packages/ui overlay contracts stay with this owner suite.
 * Owner: packages/ui Dialog, DropdownMenu, Command, Sheet, and Popover
 * contracts.
 * Boundary: public component exports only; rendered focus, trigger, motion, and
 * placement behavior belongs to rendered navigation/overlay owners.
 * Exit criteria: keep this smoke until package exports are validated by a
 * generated manifest or type-contract owner.
 */

import { describe, expect, it } from "vitest";
import {
  Command,
  CommandDialog,
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
  DropdownMenuPortal,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
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
  Sheet,
  SheetBody,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "../sheet";

type ExportSmoke = {
  component: "Dialog" | "DropdownMenu" | "Command" | "Sheet" | "Popover";
  publicExports: Array<readonly [string, unknown]>;
};

export const OVERLAY_CONTRACTS: ExportSmoke[] = [
  {
    component: "Dialog",
    publicExports: [
      ["Dialog", Dialog],
      ["DialogClose", DialogClose],
      ["DialogContent", DialogContent],
      ["DialogDescription", DialogDescription],
      ["DialogFooter", DialogFooter],
      ["DialogHeader", DialogHeader],
      ["DialogBody", DialogBody],
      ["DialogOverlay", DialogOverlay],
      ["DialogPortal", DialogPortal],
      ["DialogTitle", DialogTitle],
      ["DialogTrigger", DialogTrigger],
    ],
  },
  {
    component: "DropdownMenu",
    publicExports: [
      ["DropdownMenu", DropdownMenu],
      ["DropdownMenuPortal", DropdownMenuPortal],
      ["DropdownMenuTrigger", DropdownMenuTrigger],
      ["DropdownMenuContent", DropdownMenuContent],
      ["DropdownMenuGroup", DropdownMenuGroup],
      ["DropdownMenuLabel", DropdownMenuLabel],
      ["DropdownMenuItem", DropdownMenuItem],
      ["DropdownMenuCheckboxItem", DropdownMenuCheckboxItem],
      ["DropdownMenuRadioGroup", DropdownMenuRadioGroup],
      ["DropdownMenuRadioItem", DropdownMenuRadioItem],
      ["DropdownMenuSeparator", DropdownMenuSeparator],
      ["DropdownMenuShortcut", DropdownMenuShortcut],
      ["DropdownMenuSub", DropdownMenuSub],
      ["DropdownMenuSubTrigger", DropdownMenuSubTrigger],
      ["DropdownMenuSubContent", DropdownMenuSubContent],
    ],
  },
  {
    component: "Command",
    publicExports: [
      ["Command", Command],
      ["CommandDialog", CommandDialog],
      ["CommandInput", CommandInput],
      ["CommandList", CommandList],
      ["CommandEmpty", CommandEmpty],
      ["CommandGroup", CommandGroup],
      ["CommandItem", CommandItem],
      ["CommandShortcut", CommandShortcut],
      ["CommandSeparator", CommandSeparator],
    ],
  },
  {
    component: "Sheet",
    publicExports: [
      ["Sheet", Sheet],
      ["SheetTrigger", SheetTrigger],
      ["SheetClose", SheetClose],
      ["SheetContent", SheetContent],
      ["SheetHeader", SheetHeader],
      ["SheetBody", SheetBody],
      ["SheetFooter", SheetFooter],
      ["SheetTitle", SheetTitle],
      ["SheetDescription", SheetDescription],
    ],
  },
  {
    component: "Popover",
    publicExports: [
      ["Popover", Popover],
      ["PopoverContent", PopoverContent],
      ["PopoverDescription", PopoverDescription],
      ["PopoverHeader", PopoverHeader],
      ["PopoverTitle", PopoverTitle],
      ["PopoverTrigger", PopoverTrigger],
    ],
  },
];

describe("overlay public contract smoke", () => {
  it.each(OVERLAY_CONTRACTS)(
    "$component keeps expected public exports defined",
    ({ publicExports }) => {
      for (const [name, value] of publicExports) {
        expect(value, `${name} should remain exported`).toBeDefined();
      }
    },
  );
});
