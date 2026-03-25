import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/utils/helpers"

const cardVariants = cva(
  // base
  "bg-surface-secondary border border-border-subtle rounded-lg overflow-hidden",
  {
    variants: {
      raised: {
        true: [
          "bg-surface-raised shadow-raised",
          "border-[rgba(255,255,255,0.1)] border-t-[rgba(255,255,255,0.06)]",
        ],
        false: null,
      },
      interactive: {
        true: [
          "cursor-pointer",
          "transition-[border-color,box-shadow] duration-150 ease-[var(--ease-default)]",
          "hover:border-border-hover hover:shadow-raised",
          "focus-visible:outline-[length:var(--focus-ring-width)] focus-visible:outline-[var(--focus-ring-color)] focus-visible:outline-offset-[var(--focus-ring-offset)]",
        ],
        false: null,
      },
    },
    defaultVariants: {
      raised: false,
      interactive: false,
    },
  }
)

interface CardProps
  extends React.ComponentProps<"div">,
    VariantProps<typeof cardVariants> {}

function Card({ className, raised, interactive, ...props }: CardProps) {
  return (
    <div
      data-slot="card"
      className={cn(cardVariants({ raised, interactive }), className)}
      {...props}
    />
  )
}

function CardHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-header"
      className={cn(
        "px-4 py-3 border-b border-border-subtle flex items-center justify-between",
        className
      )}
      {...props}
    />
  )
}

function CardTitle({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-title"
      className={cn("font-medium text-heading", className)}
      {...props}
    />
  )
}

function CardDescription({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-description"
      className={cn("text-sm text-muted", className)}
      {...props}
    />
  )
}

function CardAction({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-action"
      className={cn("ml-auto", className)}
      {...props}
    />
  )
}

function CardContent({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-content"
      className={cn("p-4", className)}
      {...props}
    />
  )
}

function CardFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-footer"
      className={cn(
        "px-4 py-3 border-t border-border-subtle flex items-center gap-2",
        className
      )}
      {...props}
    />
  )
}

export {
  Card,
  CardHeader,
  CardFooter,
  CardTitle,
  CardAction,
  CardDescription,
  CardContent,
}
