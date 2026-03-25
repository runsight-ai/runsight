import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/utils/helpers"

// Design system tokens: surface-raised (elevation-overlay-surface), semantic colors
// success-9, danger-9, warning-9, info-9
const toastVariants = cva(
  "relative flex w-full items-start gap-3 rounded-radius-lg border p-4 shadow-sm",
  {
    variants: {
      variant: {
        success: "bg-surface-raised border-border-success text-success-11",
        danger: "bg-surface-raised border-border-danger text-danger-11",
        warning: "bg-surface-raised border-border-warning text-warning-11",
        info: "bg-surface-raised border-border-info text-info-11",
      },
    },
    defaultVariants: {
      variant: "info",
    },
  }
)

const toastIconColors: Record<string, string> = {
  success: "var(--success-9)",
  danger: "var(--danger-9)",
  warning: "var(--warning-9)",
  info: "var(--info-9)",
}

interface ToastProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof toastVariants> {
  title?: React.ReactNode
  description?: React.ReactNode
  onDismiss?: () => void
}

function Toast({
  className,
  variant = "info",
  title,
  description,
  onDismiss,
  children,
  ...props
}: ToastProps) {
  const isAlert = variant === "danger" || variant === "warning"

  return (
    <div
      // ARIA: role="alert" for danger/warning, role="status" for success/info
      role={isAlert ? "alert" : "status"}
      data-slot="toast"
      data-variant={variant}
      // Uses elevation-overlay-surface (same as surface-raised) for background
      style={{
        background: "var(--elevation-overlay-surface)",
        borderLeft: `3px solid ${toastIconColors[variant ?? "info"]}`,
      }}
      className={cn(toastVariants({ variant }), className)}
      {...props}
    >
      <div className="flex flex-1 flex-col gap-1">
        {title && (
          <p data-slot="toast-title" className="text-font-size-sm font-weight-medium text-heading">
            {title}
          </p>
        )}
        {description && (
          <p data-slot="toast-description" className="text-font-size-sm text-secondary">
            {description}
          </p>
        )}
        {children}
      </div>
      {onDismiss && (
        <button
          type="button"
          data-slot="toast-dismiss"
          aria-label="Dismiss"
          onClick={onDismiss}
          className="shrink-0 rounded-radius-sm p-0.5 text-muted hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus"
        >
          <svg
            aria-hidden="true"
            width="14"
            height="14"
            viewBox="0 0 14 14"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M1 1L13 13M13 1L1 13"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
        </button>
      )}
    </div>
  )
}

export { Toast, toastVariants }
