import * as React from "react"
import { ChevronLeft, ChevronRight, MoreHorizontal } from "lucide-react"

import { cn } from "@/utils/helpers"
import { Button } from "@/components/ui/button"

// ---------------------------------------------------------------------------
// Pagination root
// ---------------------------------------------------------------------------

export interface PaginationProps extends React.ComponentPropsWithoutRef<"nav"> {
  /** Current page (1-based) */
  page?: number
  /** Total number of pages */
  totalPages?: number
  /** Items per page — used for range display */
  pageSize?: number
  /** Total item count — used for range display like "1-10 of 100" */
  total?: number
  onPageChange?: (page: number) => void
}

export function Pagination({
  page = 1,
  totalPages = 1,
  pageSize = 10,
  total,
  onPageChange,
  className,
  ...props
}: PaginationProps) {
  const rangeStart = (page - 1) * pageSize + 1
  const rangeEnd = Math.min(page * pageSize, total ?? page * pageSize)

  const canGoPrev = page > 1
  const canGoNext = page < totalPages

  const pages = buildPageList(page, totalPages)

  return (
    <nav
      role="navigation"
      aria-label="pagination"
      className={cn("flex items-center gap-2 select-none", className)}
      {...props}
    >
      {/* Previous button */}
      <Button
        variant="ghost"
        size="xs"
        aria-label="Go to previous page"
        disabled={!canGoPrev}
        onClick={() => canGoPrev && onPageChange?.(page - 1)}
      >
        <ChevronLeft className="size-4" />
        <span className="sr-only">Previous</span>
      </Button>

      {/* Page number buttons */}
      <PaginationContent>
        {pages.map((entry, idx) =>
          entry === "ellipsis" ? (
            <PaginationEllipsis key={`ellipsis-${idx}`} />
          ) : (
            <PaginationItem key={entry}>
              <button
                aria-label={`Page ${entry}`}
                aria-current={entry === page ? "page" : undefined}
                onClick={() => onPageChange?.(entry as number)}
                className={cn(
                  "inline-flex size-7 items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2",
                  entry === page
                    ? "text-white [background:var(--interactive-default)]"
                    : "ghost text-text-secondary hover:text-text-primary hover:bg-surface-hover",
                )}
              >
                {entry}
              </button>
            </PaginationItem>
          )
        )}
      </PaginationContent>

      {/* Next button */}
      <Button
        variant="ghost"
        size="xs"
        aria-label="Go to next page"
        disabled={!canGoNext}
        onClick={() => canGoNext && onPageChange?.(page + 1)}
      >
        <span className="sr-only">Next</span>
        <ChevronRight className="size-4" />
      </Button>

      {/* Range display — "1-10 of 100" */}
      {total !== undefined && (
        <span className="text-sm text-text-muted whitespace-nowrap ml-2">
          {rangeStart}–{rangeEnd} of {total}
        </span>
      )}
    </nav>
  )
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function PaginationContent({
  className,
  ...props
}: React.ComponentPropsWithoutRef<"ul">) {
  return (
    <ul
      className={cn("flex items-center gap-0.5", className)}
      {...props}
    />
  )
}

function PaginationItem({
  className,
  ...props
}: React.ComponentPropsWithoutRef<"li">) {
  return <li className={cn("", className)} {...props} />
}

function PaginationEllipsis({
  className,
  ...props
}: React.ComponentPropsWithoutRef<"span">) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-flex size-7 items-center justify-center text-text-muted",
        className,
      )}
      {...props}
    >
      <MoreHorizontal className="size-4" />
      <span className="sr-only">More pages</span>
    </span>
  )
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function buildPageList(
  current: number,
  total: number,
): Array<number | "ellipsis"> {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1)
  }

  const pages: Array<number | "ellipsis"> = [1]

  if (current > 3) pages.push("ellipsis")

  const start = Math.max(2, current - 1)
  const end = Math.min(total - 1, current + 1)

  for (let i = start; i <= end; i++) pages.push(i)

  if (current < total - 2) pages.push("ellipsis")

  pages.push(total)
  return pages
}
