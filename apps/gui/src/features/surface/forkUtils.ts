/**
 * Pure utility functions for fork workflow naming.
 * No React imports — this module is framework-agnostic.
 */

/**
 * Slugify a string: lowercase, replace non-alphanumeric with hyphens,
 * collapse consecutive hyphens, trim leading/trailing hyphens.
 */
export function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/[^a-z0-9-]+/g, "")
    .replace(/-{2,}/g, "-")
    .replace(/^-|-$/g, "");
}

/**
 * Generate a 4-character alphanumeric random string using Math.random.
 */
export function shortUuid(): string {
  return Math.random().toString(36).substring(2, 6);
}

const MAX_WORKFLOW_ID_LENGTH = 100;
const FORK_PREFIX = "drft";
const FORK_SUFFIX_LENGTH = 4;
const MAX_FORK_SLUG_LENGTH =
  MAX_WORKFLOW_ID_LENGTH - FORK_PREFIX.length - FORK_SUFFIX_LENGTH - 2;

/**
 * Generate a fork draft id following the `drft-{slug}-{uuid}` convention.
 */
export function generateForkName(workflowName: string): string {
  const slug = (slugify(workflowName) || "workflow")
    .slice(0, MAX_FORK_SLUG_LENGTH)
    .replace(/-+$/g, "");
  return `${FORK_PREFIX}-${slug || "workflow"}-${shortUuid()}`;
}
