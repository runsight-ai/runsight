// Design system tokens used by BEM classes in components.css:
//   .pagination         — font-size: var(--font-size-sm); gap: var(--space-1)
//   .pagination__btn    — ghost style (transparent bg); color: var(--text-secondary)
//   .pagination__btn:hover — background: var(--surface-hover); color: var(--text-primary)
//   .pagination__btn[aria-current="page"] — background: var(--interactive-default) (surface-selected);
//                                           color: var(--text-heading); Ghost inactive state
//   .pagination__btn:disabled — opacity: 0.4
//   .pagination__info   — font-family: var(--font-mono); color: var(--text-muted)

import * as React from "react"
import { ChevronLeft, ChevronRight, MoreHorizontal } from "lucide-react"

import { cn } from "@/utils/helpers"

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
      className={cn("pagination", className)}
      {...props}
    >
      {/* Previous button */}
      <button
        type="button"
        aria-label="Go to previous page"
        disabled={!canGoPrev}
        onClick={() => canGoPrev && onPageChange?.(page - 1)}
        className="pagination__btn"
      >
        <ChevronLeft className="size-4" />
        <span className="sr-only">Previous</span>
      </button>

      {/* Page number buttons */}
      <PaginationContent>
        {pages.map((entry, idx) =>
          entry === "ellipsis" ? (
            <PaginationEllipsis key={`ellipsis-${idx}`} />
          ) : (
            <PaginationItem key={entry}>
              <button
                type="button"
                aria-label={`Page ${entry}`}
                aria-current={entry === page ? "page" : undefined}
                onClick={() => onPageChange?.(entry as number)}
                className="pagination__btn"
              >
                {entry}
              </button>
            </PaginationItem>
          )
        )}
      </PaginationContent>

      {/* Next button */}
      <button
        type="button"
        aria-label="Go to next page"
        disabled={!canGoNext}
        onClick={() => canGoNext && onPageChange?.(page + 1)}
        className="pagination__btn"
      >
        <span className="sr-only">Next</span>
        <ChevronRight className="size-4" />
      </button>

      {/* Range display — "1-10 of 100" */}
      {total !== undefined && (
        <span className="pagination__info">
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
      className={cn("pagination__btn", className)}
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
