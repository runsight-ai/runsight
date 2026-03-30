import * as React from "react"
import { Dialog as DialogPrimitive } from "@base-ui/react/dialog"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "../../utils/helpers"
import { Button } from "./button"
import { XIcon } from "lucide-react"

// ---------------------------------------------------------------------------
// Variants
// ---------------------------------------------------------------------------

const dialogOverlayVariants = cva(
  "fixed inset-0 bg-black/60 z-[var(--z-modal)] animate-[fade-in_var(--duration-150)_var(--ease-out)]"
)

const dialogContentVariants = cva(
  [
    "fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2",
    "z-[calc(var(--z-modal)+1)]",
    "bg-[var(--elevation-overlay-surface)]",
    "border border-[var(--elevation-border-raised)]",
    "rounded-[var(--radius-xl)]",
    "shadow-[var(--elevation-overlay-shadow)]",
    "flex flex-col max-h-[85vh]",
    "animate-[scale-in_var(--duration-200)_var(--ease-out)]",
  ].join(" "),
  {
    variants: {
      size: {
        sm: "w-[var(--overlay-width-sm)]",
        md: "w-[var(--overlay-width-md)]",
        lg: "w-[var(--overlay-width-lg)]",
      },
    },
    defaultVariants: {
      size: "md",
    },
  }
)

// ---------------------------------------------------------------------------
// Primitives
// ---------------------------------------------------------------------------

function Dialog({ ...props }: DialogPrimitive.Root.Props) {
  return <DialogPrimitive.Root data-slot="dialog" {...props} />
}

function DialogTrigger({ ...props }: DialogPrimitive.Trigger.Props) {
  return <DialogPrimitive.Trigger data-slot="dialog-trigger" {...props} />
}

function DialogPortal({ ...props }: DialogPrimitive.Portal.Props) {
  return <DialogPrimitive.Portal data-slot="dialog-portal" {...props} />
}

function DialogClose({ ...props }: DialogPrimitive.Close.Props) {
  return <DialogPrimitive.Close data-slot="dialog-close" {...props} />
}

function DialogOverlay({
  className,
  ...props
}: DialogPrimitive.Backdrop.Props) {
  return (
    <DialogPrimitive.Backdrop
      data-slot="dialog-overlay"
      className={cn(dialogOverlayVariants(), className)}
      {...props}
    />
  )
}

function DialogContent({
  className,
  children,
  showCloseButton = true,
  size = "md",
  ...props
}: DialogPrimitive.Popup.Props &
  VariantProps<typeof dialogContentVariants> & {
    showCloseButton?: boolean
  }) {
  return (
    <DialogPortal>
      <DialogOverlay />
      <DialogPrimitive.Popup
        data-slot="dialog-content"
        className={cn(dialogContentVariants({ size }), className)}
        {...props}
      >
        {children}
        {showCloseButton && (
          <DialogPrimitive.Close
            data-slot="dialog-close"
            render={
              <Button
                variant="ghost"
                className="absolute top-2 right-2"
                size="icon-sm"
              />
            }
          >
            <XIcon />
            <span className="sr-only">Close</span>
          </DialogPrimitive.Close>
        )}
      </DialogPrimitive.Popup>
    </DialogPortal>
  )
}

function DialogHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="dialog-header"
      className={cn(
        "flex items-center justify-between flex-shrink-0",
        "px-5 py-4",
        "border-b border-[var(--border-subtle)]",
        className
      )}
      {...props}
    />
  )
}

function DialogFooter({
  className,
  showCloseButton = false,
  children,
  ...props
}: React.ComponentProps<"div"> & {
  showCloseButton?: boolean
}) {
  return (
    <div
      data-slot="dialog-footer"
      className={cn(
        "flex items-center justify-end gap-2 flex-shrink-0",
        "px-5 py-3",
        "border-t border-[var(--border-subtle)]",
        className
      )}
      {...props}
    >
      {children}
      {showCloseButton && (
        <DialogPrimitive.Close render={<Button variant="ghost" />}>
          Close
        </DialogPrimitive.Close>
      )}
    </div>
  )
}

function DialogTitle({ className, ...props }: DialogPrimitive.Title.Props) {
  return (
    <DialogPrimitive.Title
      data-slot="dialog-title"
      className={cn(
        "text-lg font-semibold text-[var(--text-heading)]",
        className
      )}
      {...props}
    />
  )
}

function DialogDescription({
  className,
  ...props
}: DialogPrimitive.Description.Props) {
  return (
    <DialogPrimitive.Description
      data-slot="dialog-description"
      className={cn(
        "text-sm text-muted *:[a]:underline *:[a]:underline-offset-3 *:[a]:hover:text-primary",
        className
      )}
      {...props}
    />
  )
}

function DialogBody({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="dialog-body"
      className={cn("px-5 py-5 overflow-y-auto flex-1", className)}
      {...props}
    />
  )
}

export {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogBody,
  DialogOverlay,
  DialogPortal,
  DialogTitle,
  DialogTrigger,
}
