"use client"

import * as React from "react"
import { Dialog as SheetPrimitive } from "@base-ui/react/dialog"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "../../utils/helpers"
import { Button } from "./button"
import { XIcon } from "lucide-react"

// ---------------------------------------------------------------------------
// Variants
// ---------------------------------------------------------------------------

const sheetOverlayVariants = cva(
  "fixed inset-0 bg-black/50 z-[var(--z-overlay)] animate-[fade-in_var(--duration-150)_var(--ease-out)]"
)

const sheetContentVariants = cva(
  [
    "fixed z-[calc(var(--z-overlay)+1)]",
    "bg-(--elevation-overlay-surface)",
    "border border-(--elevation-border-raised)",
    "shadow-[var(--elevation-overlay-shadow)]",
    "flex flex-col overflow-y-auto",
  ].join(" "),
  {
    variants: {
      side: {
        right: [
          "top-0 right-0 bottom-0",
          "w-(--overlay-width-lg) max-w-[90vw]",
          "animate-[slide-in-right_var(--duration-200)_var(--ease-out)]",
        ].join(" "),
        bottom: [
          "left-0 right-0 bottom-0",
          "h-(--overlay-height-lg) max-h-[80vh]",
          "rounded-t-[var(--radius-xl)]",
          "animate-[slide-up_var(--duration-200)_var(--ease-out)]",
        ].join(" "),
      },
    },
    defaultVariants: {
      side: "right",
    },
  }
)

// ---------------------------------------------------------------------------
// Primitives
// ---------------------------------------------------------------------------

function Sheet({ ...props }: SheetPrimitive.Root.Props) {
  return <SheetPrimitive.Root data-slot="sheet" {...props} />
}

function SheetTrigger({ ...props }: SheetPrimitive.Trigger.Props) {
  return <SheetPrimitive.Trigger data-slot="sheet-trigger" {...props} />
}

function SheetClose({ ...props }: SheetPrimitive.Close.Props) {
  return <SheetPrimitive.Close data-slot="sheet-close" {...props} />
}

function SheetPortal({ ...props }: SheetPrimitive.Portal.Props) {
  return <SheetPrimitive.Portal data-slot="sheet-portal" {...props} />
}

function SheetOverlay({ className, ...props }: SheetPrimitive.Backdrop.Props) {
  return (
    <SheetPrimitive.Backdrop
      data-slot="sheet-overlay"
      className={cn(sheetOverlayVariants(), className)}
      {...props}
    />
  )
}

function SheetContent({
  className,
  children,
  side = "right",
  showCloseButton = true,
  ...props
}: SheetPrimitive.Popup.Props &
  VariantProps<typeof sheetContentVariants> & {
    showCloseButton?: boolean
  }) {
  return (
    <SheetPortal>
      <SheetOverlay />
      <SheetPrimitive.Popup
        data-slot="sheet-content"
        data-side={side}
        className={cn(sheetContentVariants({ side }), className)}
        {...props}
      >
        {children}
        {showCloseButton && (
          <SheetPrimitive.Close
            data-slot="sheet-close"
            render={
              <Button
                variant="ghost"
                className="absolute top-3 right-3"
                size="icon-sm"
              />
            }
          >
            <XIcon />
            <span className="sr-only">Close</span>
          </SheetPrimitive.Close>
        )}
      </SheetPrimitive.Popup>
    </SheetPortal>
  )
}

function SheetHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="sheet-header"
      className={cn(
        "flex items-center justify-between flex-shrink-0",
        "px-5 py-4",
        "border-b border-(--border-subtle)",
        className
      )}
      {...props}
    />
  )
}

function SheetBody({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="sheet-body"
      className={cn("px-5 py-5 flex-1 overflow-y-auto", className)}
      {...props}
    />
  )
}

function SheetFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="sheet-footer"
      className={cn("mt-auto flex flex-col gap-2 p-4", className)}
      {...props}
    />
  )
}

function SheetTitle({ className, ...props }: SheetPrimitive.Title.Props) {
  return (
    <SheetPrimitive.Title
      data-slot="sheet-title"
      className={cn("text-base font-medium text-primary", className)}
      {...props}
    />
  )
}

function SheetDescription({
  className,
  ...props
}: SheetPrimitive.Description.Props) {
  return (
    <SheetPrimitive.Description
      data-slot="sheet-description"
      className={cn("text-sm text-muted", className)}
      {...props}
    />
  )
}

export {
  Sheet,
  SheetTrigger,
  SheetClose,
  SheetContent,
  SheetHeader,
  SheetBody,
  SheetFooter,
  SheetTitle,
  SheetDescription,
}
