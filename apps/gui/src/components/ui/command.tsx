import * as React from "react"
import { Command as CommandPrimitive } from "cmdk"

import { cn } from "@/utils/helpers"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { SearchIcon, CheckIcon } from "lucide-react"

// ---------------------------------------------------------------------------
// Command palette — pure Tailwind
// Spec: fixed top-20%, centered, overlay-width-sm, elevation-overlay-surface,
//       elevation-border-raised, overlay-shadow, z-modal, radius-2xl
// ---------------------------------------------------------------------------

/** Base command palette container (also used stand-alone without a dialog). */
function Command({
  className,
  ...props
}: React.ComponentProps<typeof CommandPrimitive>) {
  return (
    <CommandPrimitive
      data-slot="command"
      className={cn(
        // position (when used stand-alone / inside CommandDialog)
        "flex flex-col",
        // elevation surface
        "bg-(--elevation-overlay-surface)",
        "border border-(--elevation-border-raised)",
        "rounded-[var(--radius-2xl)]",
        "shadow-[var(--elevation-overlay-shadow)]",
        className
      )}
      {...props}
    />
  )
}

/** Full-screen command dialog — wraps DialogContent + Command. */
function CommandDialog({
  title = "Command Palette",
  description = "Search for a command to run...",
  children,
  className,
  showCloseButton = false,
  ...props
}: Omit<React.ComponentProps<typeof Dialog>, "children"> & {
  title?: string
  description?: string
  className?: string
  showCloseButton?: boolean
  children: React.ReactNode
}) {
  return (
    <Dialog {...props}>
      <DialogHeader className="sr-only">
        <DialogTitle>{title}</DialogTitle>
        <DialogDescription>{description}</DialogDescription>
      </DialogHeader>
      <DialogContent
        className={cn(
          // position override for palette-style (top-20% instead of center)
          "fixed! top-[20%]! -translate-y-0! left-1/2! -translate-x-1/2!",
          "w-[min(var(--overlay-width-sm),90vw)] max-h-(--overlay-height-xl)",
          // no default dialog padding — command sub-components handle it
          "p-0",
          className
        )}
        size="md"
        showCloseButton={showCloseButton}
      >
        {children}
      </DialogContent>
    </Dialog>
  )
}

function CommandInput({
  className,
  ...props
}: React.ComponentProps<typeof CommandPrimitive.Input>) {
  return (
    <div
      data-slot="command-input-wrapper"
      className="flex items-center gap-2 px-4 py-3 border-b border-(--border-subtle)"
    >
      <SearchIcon className="text-(--text-muted) flex-shrink-0" />
      <CommandPrimitive.Input
        data-slot="command-input"
        className={cn(
          "flex-1 bg-transparent border-none outline-none",
          "font-[var(--font-body)] text-[length:var(--font-size-lg)] text-(--text-heading)",
          "placeholder:text-(--text-muted)",
          className
        )}
        {...props}
      />
    </div>
  )
}

function CommandList({
  className,
  ...props
}: React.ComponentProps<typeof CommandPrimitive.List>) {
  return (
    <CommandPrimitive.List
      data-slot="command-list"
      className={cn(
        "overflow-y-auto p-2 max-h-[calc(var(--overlay-height-xl)-60px)]",
        className
      )}
      {...props}
    />
  )
}

function CommandEmpty({
  className,
  ...props
}: React.ComponentProps<typeof CommandPrimitive.Empty>) {
  return (
    <CommandPrimitive.Empty
      data-slot="command-empty"
      className={cn("py-6 text-center text-sm", className)}
      {...props}
    />
  )
}

function CommandGroup({
  className,
  ...props
}: React.ComponentProps<typeof CommandPrimitive.Group>) {
  return (
    <CommandPrimitive.Group
      data-slot="command-group"
      className={cn(
        "overflow-hidden",
        // target the cmdk group heading element
        "**:[[cmdk-group-heading]]:font-mono **:[[cmdk-group-heading]]:text-[length:var(--font-size-2xs)]",
        "**:[[cmdk-group-heading]]:font-medium **:[[cmdk-group-heading]]:tracking-[var(--tracking-wider)]",
        "**:[[cmdk-group-heading]]:uppercase **:[[cmdk-group-heading]]:text-(--text-muted)",
        "**:[[cmdk-group-heading]]:px-2 **:[[cmdk-group-heading]]:pb-1 **:[[cmdk-group-heading]]:pt-2",
        className
      )}
      {...props}
    />
  )
}

function CommandSeparator({
  className,
  ...props
}: React.ComponentProps<typeof CommandPrimitive.Separator>) {
  return (
    <CommandPrimitive.Separator
      data-slot="command-separator"
      className={cn("-mx-1 h-px bg-(--border-default)", className)}
      {...props}
    />
  )
}

function CommandItem({
  className,
  children,
  ...props
}: React.ComponentProps<typeof CommandPrimitive.Item>) {
  return (
    <CommandPrimitive.Item
      data-slot="command-item"
      className={cn(
        "flex items-center gap-2",
        "px-2 py-2 rounded-[var(--radius-md)]",
        "cursor-pointer",
        "text-[length:var(--font-size-md)] text-(--text-primary)",
        "transition-[background] duration-[var(--duration-50)]",
        "hover:bg-(--surface-hover)",
        "aria-selected:bg-(--surface-hover)",
        "outline-none",
        className
      )}
      {...props}
    >
      {children}
      <CheckIcon className="ml-auto opacity-0 group-has-data-[slot=command-shortcut]/command-item:hidden group-data-[checked=true]/command-item:opacity-100" />
    </CommandPrimitive.Item>
  )
}

function CommandShortcut({
  className,
  ...props
}: React.ComponentProps<"span">) {
  return (
    <span
      data-slot="command-shortcut"
      className={cn(
        "font-mono text-[length:var(--font-size-2xs)] text-(--text-muted)",
        className
      )}
      {...props}
    />
  )
}

export {
  Command,
  CommandDialog,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandShortcut,
  CommandSeparator,
}
