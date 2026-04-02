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

/**
 * Generate a fork draft name following the `drft-{slug}-{uuid}` convention.
 */
export function generateForkName(workflowName: string): string {
  return `drft-${slugify(workflowName)}-${shortUuid()}`;
}
