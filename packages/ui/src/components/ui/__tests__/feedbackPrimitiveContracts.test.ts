import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

/**
 * Governance: packages/ui feedback primitive contract coverage stays in a compact owner suite.
 * Owner: packages/ui design-system primitives for Spinner, Skeleton, Progress, StatusDot, and Toast.
 * Boundary: source-text contract checks for files, exports, variants, tokens, animation hooks, and ARIA.
 * Exit criteria: keep this suite table-driven until equivalent runtime or rendered owner coverage replaces it.
 */

type ComponentFile = {
  component: string;
  file: string;
};

type ContractCheck = ComponentFile & {
  contract: string;
  pattern: RegExp;
};

const UI_DIR = resolve(dirname(fileURLToPath(import.meta.url)), "..");

function componentPath(filename: string): string {
  return resolve(UI_DIR, filename);
}

function readComponent(filename: string): string {
  return readFileSync(componentPath(filename), "utf-8");
}

function variantKey(key: string): RegExp {
  return new RegExp(`["']?${key}["']?\\s*:`);
}

export const FEEDBACK_PRIMITIVE_CONTRACTS = {
  files: [
    { component: "Spinner", file: "spinner.tsx" },
    { component: "Skeleton", file: "skeleton.tsx" },
    { component: "Progress", file: "progress.tsx" },
    { component: "StatusDot", file: "status-dot.tsx" },
    { component: "Toast", file: "toast.tsx" },
  ] satisfies ComponentFile[],
  required: [
    { component: "Spinner", file: "spinner.tsx", contract: "named export", pattern: /export.*\bSpinner\b/ },
    { component: "Spinner", file: "spinner.tsx", contract: "sm size", pattern: variantKey("sm") },
    { component: "Spinner", file: "spinner.tsx", contract: "md size", pattern: variantKey("md") },
    { component: "Spinner", file: "spinner.tsx", contract: "lg size", pattern: variantKey("lg") },
    { component: "Spinner", file: "spinner.tsx", contract: "default variant", pattern: variantKey("default") },
    { component: "Spinner", file: "spinner.tsx", contract: "accent variant", pattern: variantKey("accent") },
    { component: "Spinner", file: "spinner.tsx", contract: "icon size token", pattern: /icon-size/ },
    { component: "Spinner", file: "spinner.tsx", contract: "muted text token", pattern: /text-muted/ },
    { component: "Spinner", file: "spinner.tsx", contract: "interactive token", pattern: /interactive/ },
    { component: "Spinner", file: "spinner.tsx", contract: "thick border token", pattern: /border-width-thick/ },
    { component: "Spinner", file: "spinner.tsx", contract: "full radius token", pattern: /radius-full/ },
    { component: "Spinner", file: "spinner.tsx", contract: "spin animation", pattern: /spin/ },
    { component: "Spinner", file: "spinner.tsx", contract: "status role", pattern: /role\s*=\s*["']status["']/ },
    { component: "Spinner", file: "spinner.tsx", contract: "accessible label", pattern: /aria-label/ },
    { component: "Skeleton", file: "skeleton.tsx", contract: "named export", pattern: /export.*\bSkeleton\b/ },
    { component: "Skeleton", file: "skeleton.tsx", contract: "text variant", pattern: variantKey("text") },
    { component: "Skeleton", file: "skeleton.tsx", contract: "small text variant", pattern: /["']?text-sm["']?\s*:|text.sm/ },
    { component: "Skeleton", file: "skeleton.tsx", contract: "heading variant", pattern: variantKey("heading") },
    { component: "Skeleton", file: "skeleton.tsx", contract: "avatar variant", pattern: variantKey("avatar") },
    { component: "Skeleton", file: "skeleton.tsx", contract: "button variant", pattern: variantKey("button") },
    { component: "Skeleton", file: "skeleton.tsx", contract: "neutral background token", pattern: /neutral-3/ },
    { component: "Skeleton", file: "skeleton.tsx", contract: "neutral highlight token", pattern: /neutral-4/ },
    { component: "Skeleton", file: "skeleton.tsx", contract: "loading animation", pattern: /shimmer|pulse|animate/ },
    { component: "Skeleton", file: "skeleton.tsx", contract: "busy state", pattern: /aria-busy/ },
    { component: "Skeleton", file: "skeleton.tsx", contract: "accessible label", pattern: /aria-label/ },
    { component: "Progress", file: "progress.tsx", contract: "named export", pattern: /export.*\bProgress\b/ },
    { component: "Progress", file: "progress.tsx", contract: "default variant", pattern: variantKey("default") },
    { component: "Progress", file: "progress.tsx", contract: "md size or variant", pattern: variantKey("md") },
    { component: "Progress", file: "progress.tsx", contract: "success variant", pattern: variantKey("success") },
    { component: "Progress", file: "progress.tsx", contract: "danger variant", pattern: variantKey("danger") },
    { component: "Progress", file: "progress.tsx", contract: "indeterminate state", pattern: /indeterminate/ },
    { component: "Progress", file: "progress.tsx", contract: "neutral track token", pattern: /neutral-3/ },
    { component: "Progress", file: "progress.tsx", contract: "interactive fill token", pattern: /interactive/ },
    { component: "Progress", file: "progress.tsx", contract: "success fill token", pattern: /success-9/ },
    { component: "Progress", file: "progress.tsx", contract: "danger fill token", pattern: /danger-9/ },
    { component: "Progress", file: "progress.tsx", contract: "progressbar role", pattern: /role\s*=\s*["']progressbar["']/ },
    { component: "Progress", file: "progress.tsx", contract: "current value attribute", pattern: /aria-valuenow/ },
    { component: "Progress", file: "progress.tsx", contract: "minimum value attribute", pattern: /aria-valuemin/ },
    { component: "Progress", file: "progress.tsx", contract: "maximum value attribute", pattern: /aria-valuemax/ },
    { component: "StatusDot", file: "status-dot.tsx", contract: "named export", pattern: /export.*\bStatusDot\b/ },
    { component: "StatusDot", file: "status-dot.tsx", contract: "neutral variant", pattern: variantKey("neutral") },
    { component: "StatusDot", file: "status-dot.tsx", contract: "active variant", pattern: variantKey("active") },
    { component: "StatusDot", file: "status-dot.tsx", contract: "success variant", pattern: variantKey("success") },
    { component: "StatusDot", file: "status-dot.tsx", contract: "warning variant", pattern: variantKey("warning") },
    { component: "StatusDot", file: "status-dot.tsx", contract: "danger variant", pattern: variantKey("danger") },
    { component: "StatusDot", file: "status-dot.tsx", contract: "neutral color token", pattern: /neutral-9/ },
    { component: "StatusDot", file: "status-dot.tsx", contract: "active color token", pattern: /info-9/ },
    { component: "StatusDot", file: "status-dot.tsx", contract: "success color token", pattern: /success-9/ },
    { component: "StatusDot", file: "status-dot.tsx", contract: "warning color token", pattern: /warning-9/ },
    { component: "StatusDot", file: "status-dot.tsx", contract: "danger color token", pattern: /danger-9/ },
    { component: "StatusDot", file: "status-dot.tsx", contract: "full radius token", pattern: /radius-full/ },
    { component: "StatusDot", file: "status-dot.tsx", contract: "space sizing token", pattern: /space-2/ },
    { component: "StatusDot", file: "status-dot.tsx", contract: "pulse animation", pattern: /pulse/ },
    { component: "StatusDot", file: "status-dot.tsx", contract: "spin animation", pattern: /spin/ },
    { component: "Toast", file: "toast.tsx", contract: "named export", pattern: /export.*\bToast\b/ },
    { component: "Toast", file: "toast.tsx", contract: "success variant", pattern: variantKey("success") },
    { component: "Toast", file: "toast.tsx", contract: "danger variant", pattern: variantKey("danger") },
    { component: "Toast", file: "toast.tsx", contract: "warning variant", pattern: variantKey("warning") },
    { component: "Toast", file: "toast.tsx", contract: "info variant", pattern: variantKey("info") },
    { component: "Toast", file: "toast.tsx", contract: "raised surface token", pattern: /surface-raised|elevation-overlay-surface/ },
    { component: "Toast", file: "toast.tsx", contract: "success token", pattern: /success/ },
    { component: "Toast", file: "toast.tsx", contract: "danger token", pattern: /danger/ },
    { component: "Toast", file: "toast.tsx", contract: "warning token", pattern: /warning/ },
    { component: "Toast", file: "toast.tsx", contract: "info token", pattern: /info/ },
    { component: "Toast", file: "toast.tsx", contract: "title support", pattern: /title|Title/ },
    { component: "Toast", file: "toast.tsx", contract: "description support", pattern: /description|Description/ },
    { component: "Toast", file: "toast.tsx", contract: "dismiss support", pattern: /dismiss|Dismiss|close|Close/ },
    { component: "Toast", file: "toast.tsx", contract: "status or alert role", pattern: /role\s*=\s*["'](status|alert)["']/ },
  ] satisfies ContractCheck[],
};

describe("feedback primitive contracts", () => {
  it.each(FEEDBACK_PRIMITIVE_CONTRACTS.files)("$component has a component file", ({ file }) => {
    expect(existsSync(componentPath(file))).toBe(true);
  });

  it.each(FEEDBACK_PRIMITIVE_CONTRACTS.required)(
    "$component provides $contract",
    ({ file, pattern }) => {
      expect(readComponent(file)).toMatch(pattern);
    },
  );
});
