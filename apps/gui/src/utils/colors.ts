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
      return "bg-[var(--success-12)] text-[var(--success-9)]";
    case "javascript":
      return "bg-[var(--warning-12)] text-[var(--warning-9)]";
    case "shell":
      return "bg-[var(--surface-raised)] text-[var(--text-muted)]";
    case "http":
      return "bg-[var(--info-3)] text-[var(--info-9)]";
    case "prompt":
      return "bg-[var(--accent-3)] text-[var(--interactive-default)]";
    case "condition":
      return "bg-[var(--error-12)] text-[var(--danger-9)]";
    case "loop":
      return "bg-[var(--accent-alt-12)] text-[var(--accent-alt)]";
    default:
      return "bg-[var(--neutral-3)] text-[var(--text-muted)]";
  }
}

// ── Run/workflow status → Tailwind class string ─────────────────────────────

export function getStatusColor(status: string): string {
  switch (status.toLowerCase()) {
    case "completed":
    case "success":
      return "bg-[var(--success-12)] text-[var(--success-9)]";
    case "failed":
    case "error":
      return "bg-[var(--error-12)] text-[var(--danger-9)]";
    case "running":
      return "bg-[var(--info-3)] text-[var(--info-9)]";
    case "pending":
    case "idle":
    default:
      return "bg-[var(--neutral-3)] text-[var(--text-muted)]";
  }
}

// ── Run status string → StatusVariant ───────────────────────────────────────

/** Map a raw run-node status string to a canonical RunNodeData status. */
export function mapRunStatus(
  status: string,
): "idle" | "pending" | "running" | "completed" | "failed" | "paused" {
  switch (status) {
    case "completed":
    case "success":
      return "completed";
    case "failed":
    case "error":
      return "failed";
    case "running":
      return "running";
    case "pending":
    default:
      return "pending";
  }
}

/** Map a block_type string to an icon key for canvas nodes. */
export function getIconForBlockType(blockType: string): string {
  if (blockType.includes("agent") || blockType.includes("llm")) return "user";
  if (blockType.includes("condition") || blockType.includes("if"))
    return "layers";
  if (blockType.includes("input") || blockType.includes("output"))
    return "mail";
  return "server";
}

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
