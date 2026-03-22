/**
 * Shared color/variant utilities.
 *
 * Pure functions — no JSX, no side-effects.
 */

import type { StatusVariant } from "@/components/shared";

// ── Step type → Tailwind class string ───────────────────────────────────────

export function getStepTypeColor(type: string): string {
  switch (type.toLowerCase()) {
    case "python":
      return "bg-[var(--success-12)] text-[var(--success)]";
    case "javascript":
      return "bg-[var(--warning-12)] text-[var(--warning)]";
    case "shell":
      return "bg-[var(--surface-elevated)] text-[var(--muted-foreground)]";
    case "http":
      return "bg-[var(--running-12)] text-[var(--running)]";
    case "prompt":
      return "bg-[var(--primary-12)] text-[var(--primary)]";
    case "condition":
      return "bg-[var(--error-12)] text-[var(--error)]";
    case "loop":
      return "bg-[var(--accent-alt-12)] text-[var(--accent-alt)]";
    default:
      return "bg-[var(--muted-12)] text-[var(--muted-foreground)]";
  }
}

// ── Run/workflow status → Tailwind class string ─────────────────────────────

export function getStatusColor(status: string): string {
  switch (status.toLowerCase()) {
    case "completed":
    case "success":
      return "bg-[var(--success-12)] text-[var(--success)]";
    case "failed":
    case "error":
      return "bg-[var(--error-12)] text-[var(--error)]";
    case "running":
      return "bg-[var(--running-12)] text-[var(--running)]";
    case "pending":
    case "idle":
    default:
      return "bg-[var(--muted-12)] text-[var(--muted-foreground)]";
  }
}

// ── Run status string → StatusVariant ───────────────────────────────────────

export function mapRunStatusToVariant(status: string): StatusVariant {
  switch (status.toLowerCase()) {
    case "completed":
    case "success":
      return "success";
    case "failed":
    case "killed":
      return "error";
    case "running":
      return "running";
    case "paused":
      return "warning";
    case "cancelled":
      return "cancelled";
    case "pending":
    case "idle":
    default:
      return "pending";
  }
}
