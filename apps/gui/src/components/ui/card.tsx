// Design system tokens used by BEM classes in components.css:
//   .card          — border: var(--border-subtle); border-radius: var(--radius-lg);
//                    background: var(--surface-secondary); overflow: hidden
//   .card__header  — padding: var(--space-3) var(--space-4); border-bottom: var(--border-subtle)
//   .card__body    — padding: var(--space-4)
//   .card__footer  — padding: var(--space-3) var(--space-4); border-top: var(--border-subtle)
//   .card--raised  — background: var(--elevation-raised-surface); box-shadow: raised
//   .card--interactive — cursor pointer, hover border-color: var(--border-hover)
// CardTitle uses text-heading for header text color.

import * as React from "react"

import { cn } from "@/utils/helpers"

interface CardProps extends React.ComponentProps<"div"> {
  raised?: boolean
  interactive?: boolean
}

function Card({
  className,
  raised,
  interactive,
  ...props
}: CardProps) {
  return (
    <div
      data-slot="card"
      className={cn(
        "card",
        raised && "card--raised",
        interactive && "card--interactive",
        className
      )}
      {...props}
    />
  )
}

function CardHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-header"
      className={cn("card__header", className)}
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
      className={cn("card__body", className)}
      {...props}
    />
  )
}

function CardFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-footer"
      className={cn("card__footer", className)}
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
