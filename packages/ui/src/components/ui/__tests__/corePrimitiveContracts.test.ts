import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

/**
 * Governance: packages/ui core primitive contract coverage stays in a compact owner suite.
 * Owner: packages/ui design-system primitives for Button, Badge, Input, Textarea, Label, and Tooltip.
 * Boundary: source-text contract checks for public variants, token usage, and required adapter patterns.
 * Exit criteria: keep this suite table-driven until equivalent runtime or rendered owner coverage replaces it.
 */

type ContractCheck = {
  component: string;
  file: string;
  contract: string;
  pattern: RegExp;
};

type RejectedContractCheck = ContractCheck;

const UI_DIR = resolve(dirname(fileURLToPath(import.meta.url)), "..");

function readComponent(filename: string): string {
  return readFileSync(resolve(UI_DIR, filename), "utf-8");
}

function variantKey(key: string): RegExp {
  return new RegExp(`["']?${key}["']?\\s*:`);
}

export const CORE_PRIMITIVE_CONTRACTS = {
  required: [
    { component: "Button", file: "button.tsx", contract: "primary variant", pattern: variantKey("primary") },
    { component: "Button", file: "button.tsx", contract: "secondary variant", pattern: variantKey("secondary") },
    { component: "Button", file: "button.tsx", contract: "ghost variant", pattern: variantKey("ghost") },
    { component: "Button", file: "button.tsx", contract: "danger variant", pattern: variantKey("danger") },
    { component: "Button", file: "button.tsx", contract: "icon-only variant", pattern: /["']icon-only["']\s*:/ },
    { component: "Button", file: "button.tsx", contract: "xs size", pattern: variantKey("xs") },
    { component: "Button", file: "button.tsx", contract: "sm size", pattern: variantKey("sm") },
    { component: "Button", file: "button.tsx", contract: "md size", pattern: variantKey("md") },
    { component: "Button", file: "button.tsx", contract: "lg size", pattern: variantKey("lg") },
    { component: "Button", file: "button.tsx", contract: "compact icon size", pattern: /["']icon-sm["']\s*:/ },
    { component: "Button", file: "button.tsx", contract: "interactive token", pattern: /interactive/ },
    { component: "Button", file: "button.tsx", contract: "danger token family", pattern: /danger/ },
    { component: "Button", file: "button.tsx", contract: "medium radius token", pattern: /radius-md|rounded-md/ },
    { component: "Button", file: "button.tsx", contract: "medium text token", pattern: /font-size-md|text-md/ },
    { component: "Button", file: "button.tsx", contract: "medium weight token", pattern: /font-weight-medium|font-medium/ },
    { component: "Button", file: "button.tsx", contract: "tertiary surface token", pattern: /surface-tertiary/ },
    { component: "Button", file: "button.tsx", contract: "on-accent text token", pattern: /text-on-accent/ },
    { component: "Button", file: "button.tsx", contract: "loading state", pattern: /loading|aria-busy/i },
    { component: "Button", file: "button.tsx", contract: "Base UI button adapter", pattern: /@base-ui\/react\/button/ },
    { component: "Badge", file: "badge.tsx", contract: "accent variant", pattern: variantKey("accent") },
    { component: "Badge", file: "badge.tsx", contract: "success variant", pattern: variantKey("success") },
    { component: "Badge", file: "badge.tsx", contract: "warning variant", pattern: variantKey("warning") },
    { component: "Badge", file: "badge.tsx", contract: "danger variant", pattern: variantKey("danger") },
    { component: "Badge", file: "badge.tsx", contract: "info variant", pattern: variantKey("info") },
    { component: "Badge", file: "badge.tsx", contract: "neutral variant", pattern: variantKey("neutral") },
    { component: "Badge", file: "badge.tsx", contract: "outline variant", pattern: variantKey("outline") },
    { component: "Badge", file: "badge.tsx", contract: "mono font token", pattern: /font-mono/ },
    { component: "Badge", file: "badge.tsx", contract: "2xs text token", pattern: /font-size-2xs|text-2xs/ },
    { component: "Badge", file: "badge.tsx", contract: "full radius token", pattern: /radius-full|rounded-full/ },
    { component: "Badge", file: "badge.tsx", contract: "accent color token", pattern: /accent-[0-9]/ },
    { component: "Badge", file: "badge.tsx", contract: "success color token", pattern: /success-[0-9]/ },
    { component: "Badge", file: "badge.tsx", contract: "warning color token", pattern: /warning-[0-9]/ },
    { component: "Badge", file: "badge.tsx", contract: "danger color token", pattern: /danger-[0-9]/ },
    { component: "Badge", file: "badge.tsx", contract: "info color token", pattern: /info-[0-9]/ },
    { component: "Badge", file: "badge.tsx", contract: "wide tracking token", pattern: /tracking-wide/ },
    { component: "Badge", file: "badge.tsx", contract: "dot indicator", pattern: /\bdot\b/ },
    { component: "Badge", file: "badge.tsx", contract: "Base UI mergeProps adapter", pattern: /@base-ui\/react\/merge-props/ },
    { component: "Badge", file: "badge.tsx", contract: "Base UI render adapter", pattern: /@base-ui\/react\/use-render/ },
    { component: "Input", file: "input.tsx", contract: "small control height token", pattern: /control-height-sm/ },
    { component: "Input", file: "input.tsx", contract: "medium text token", pattern: /font-size-md|text-md/ },
    { component: "Input", file: "input.tsx", contract: "default border token", pattern: /border-default/ },
    { component: "Input", file: "input.tsx", contract: "focus border token", pattern: /border-focus/ },
    { component: "Input", file: "input.tsx", contract: "surface token", pattern: /surface-primary|surface-tertiary/ },
    { component: "Textarea", file: "textarea.tsx", contract: "small control height token", pattern: /control-height-sm/ },
    { component: "Textarea", file: "textarea.tsx", contract: "medium text token", pattern: /font-size-md|text-md/ },
    { component: "Textarea", file: "textarea.tsx", contract: "default border token", pattern: /border-default/ },
    { component: "Textarea", file: "textarea.tsx", contract: "focus border token", pattern: /border-focus/ },
    { component: "Textarea", file: "textarea.tsx", contract: "surface token", pattern: /surface-primary|surface-tertiary/ },
    { component: "Label", file: "label.tsx", contract: "small text token", pattern: /font-size-sm|text-sm/ },
    { component: "Label", file: "label.tsx", contract: "medium weight token", pattern: /font-weight-medium|font-medium/ },
    { component: "Label", file: "label.tsx", contract: "text color token", pattern: /text-primary|text-secondary/ },
    { component: "Tooltip", file: "tooltip.tsx", contract: "raised surface token", pattern: /surface-raised/ },
    { component: "Tooltip", file: "tooltip.tsx", contract: "primary text token", pattern: /\btext-primary\b/ },
    { component: "Tooltip", file: "tooltip.tsx", contract: "xs text token", pattern: /font-size-xs/ },
  ] satisfies ContractCheck[],
  rejected: [
    { component: "Button", file: "button.tsx", contract: "default button variant key", pattern: /variant:\s*\{[^}]*\bdefault\s*:/s },
    { component: "Button", file: "button.tsx", contract: "destructive button variant key", pattern: /\bdestructive\s*:/ },
    { component: "Button", file: "button.tsx", contract: "outline button variant key", pattern: /\boutline\s*:/ },
    { component: "Button", file: "button.tsx", contract: "link button variant key", pattern: /\blink\s*:/ },
    { component: "Button", file: "button.tsx", contract: "standalone icon size key", pattern: /["']?icon["']?\s*:/ },
    { component: "Button", file: "button.tsx", contract: "icon-xs size key", pattern: /["']icon-xs["']\s*:/ },
    { component: "Button", file: "button.tsx", contract: "icon-lg size key", pattern: /["']icon-lg["']\s*:/ },
    { component: "Button", file: "button.tsx", contract: "default button size key", pattern: /size:\s*\{[^}]*\bdefault\s*:/s },
    { component: "Badge", file: "badge.tsx", contract: "default badge variant key", pattern: /variant:\s*\{[^}]*\bdefault\s*:/s },
    { component: "Badge", file: "badge.tsx", contract: "destructive badge variant key", pattern: /\bdestructive\s*:/ },
    { component: "Badge", file: "badge.tsx", contract: "ghost badge variant key", pattern: /\bghost\s*:/ },
    { component: "Badge", file: "badge.tsx", contract: "link badge variant key", pattern: /\blink\s*:/ },
    { component: "Badge", file: "badge.tsx", contract: "secondary badge variant key", pattern: /\bsecondary\s*:/ },
    { component: "Tooltip", file: "tooltip.tsx", contract: "text-primary background class", pattern: /\bbg-text-primary\b/ },
    { component: "Tooltip", file: "tooltip.tsx", contract: "surface-primary text class", pattern: /\btext-surface-primary\b/ },
    { component: "Tooltip", file: "tooltip.tsx", contract: "text-primary arrow background", pattern: /bg-text-primary.*Arrow|Arrow.*bg-text-primary/s },
  ] satisfies RejectedContractCheck[],
};

describe("core primitive contracts", () => {
  it.each(CORE_PRIMITIVE_CONTRACTS.required)(
    "$component provides $contract",
    ({ file, pattern }) => {
      expect(readComponent(file)).toMatch(pattern);
    },
  );

  it.each(CORE_PRIMITIVE_CONTRACTS.rejected)(
    "$component omits $contract",
    ({ file, pattern }) => {
      expect(readComponent(file)).not.toMatch(pattern);
    },
  );
});
