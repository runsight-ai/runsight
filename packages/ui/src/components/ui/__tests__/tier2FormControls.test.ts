/**
 * Tier 2 form control component coverage.
 *
 * Validates that Select and Switch have been updated to use the
 * Runsight design system tokens, and that Checkbox, Radio, and Slider have
 * been created to match the design system component spec.
 *
 * Tests read component source files as strings and verify:
 *   1. Existing components (select, switch): required tokens present
 *   2. New components (checkbox, radio, slider): file exists, exports, tokens, ARIA
 */

import { describe, it, expect } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

// ---------------------------------------------------------------------------
// Paths
// ---------------------------------------------------------------------------

const UI_DIR = resolve(__dirname, "..");
function componentExists(filename: string): boolean {
  return existsSync(resolve(UI_DIR, filename));
}

function readComponent(filename: string): string {
  return readFileSync(resolve(UI_DIR, filename), "utf-8");
}

// ===========================================================================
// 1. SELECT — trigger height token
// ===========================================================================

describe("Select — control-height token on trigger", () => {
  it("uses --control-height-sm or control-height-sm for trigger height", () => {
    const source = readComponent("select.tsx");
    // Spec: Height uses --control-height-sm design token on SelectTrigger
    // Current state: uses data-[size=sm]:h-7 (hardcoded px, no DS token)
    expect(source).toMatch(/control-height-sm/);
  });
});

// ===========================================================================
// 2. SELECT — border tokens
// ===========================================================================

describe("Select — border tokens", () => {
  it("uses border-default token for trigger border", () => {
    const source = readComponent("select.tsx");
    // Spec: border uses --border-default
    // Current state: already has border-border-default — passes
    expect(source).toMatch(/border-default/);
  });

  it("uses border-hover token for trigger hover state", () => {
    const source = readComponent("select.tsx");
    // Spec: hover border uses --border-hover
    // Current state: no hover border token present
    expect(source).toMatch(/border-hover/);
  });
});

// ===========================================================================
// 3. SELECT — background tokens
// ===========================================================================

describe("Select — background tokens", () => {
  it("uses surface-tertiary token for trigger background", () => {
    const source = readComponent("select.tsx");
    // Spec: trigger background is --surface-tertiary
    // Current state: trigger uses bg-transparent (not surface-tertiary)
    expect(source).toMatch(/surface-tertiary/);
  });

  it("uses surface-overlay token for dropdown content background", () => {
    const source = readComponent("select.tsx");
    // Spec: dropdown popup uses --surface-overlay
    // Current state: already has bg-surface-overlay — passes
    expect(source).toMatch(/surface-overlay/);
  });
});

// ===========================================================================
// 4. SELECT — text token
// ===========================================================================

describe("Select — text token", () => {
  it("uses text-primary token for selected value text", () => {
    const source = readComponent("select.tsx");
    // Spec: text uses --text-primary
    // Current state: uses text-primary via Tailwind but without DS token form
    expect(source).toMatch(/text-primary/);
  });
});

// ===========================================================================
// 5. SELECT — elevation shadow on dropdown
// ===========================================================================

describe("Select — elevation shadow on dropdown", () => {
  it("uses elevation-overlay-shadow or shadow-overlay token on dropdown content", () => {
    const source = readComponent("select.tsx");
    // Spec: dropdown uses --elevation-overlay-shadow
    // Current state: uses generic shadow-md (not the DS elevation token)
    expect(source).toMatch(/elevation-overlay-shadow|shadow-overlay/);
  });
});

// ===========================================================================
// 6. SWITCH — track off-state token
// ===========================================================================

describe("Switch — track off-state token", () => {
  it("uses neutral-5 or neutral-6 token for the unchecked track", () => {
    const source = readComponent("switch.tsx");
    // Spec: unchecked track background is --neutral-5 or --neutral-6
    // Current state: uses bg-input (old token — not neutral-5/neutral-6)
    expect(source).toMatch(/neutral-5|neutral-6/);
  });
});

// ===========================================================================
// 7. SWITCH — track on-state token
// ===========================================================================

describe("Switch — track on-state token", () => {
  it("uses interactive-default token for the checked track", () => {
    const source = readComponent("switch.tsx");
    // Spec: checked track background is --interactive-default
    // Current state: uses bg-interactive (generic, not the explicit DS token name)
    expect(source).toMatch(/interactive-default/);
  });
});

// ===========================================================================
// 8. SWITCH — thumb token
// ===========================================================================

describe("Switch — thumb token", () => {
  it("uses neutral-12 token for the switch thumb", () => {
    const source = readComponent("switch.tsx");
    // Spec: thumb background is --neutral-12
    // Current state: uses bg-surface-primary (not neutral-12)
    expect(source).toMatch(/neutral-12/);
  });
});

// ===========================================================================
// 9. SWITCH — old input token removed
// ===========================================================================

describe("Switch — old bg-input token removed", () => {
  it("does not use bg-input for the unchecked track (replaced by neutral-5/neutral-6)", () => {
    const source = readComponent("switch.tsx");
    // Old: data-unchecked:bg-input — must be replaced with neutral-5/neutral-6
    expect(source).not.toMatch(/data-unchecked:bg-input\b/);
  });
});

// ===========================================================================
// 10. CHECKBOX — file exists
// ===========================================================================

describe("Checkbox — component file exists", () => {
  it("checkbox.tsx exists in src/components/ui/", () => {
    expect(componentExists("checkbox.tsx")).toBe(true);
  });
});

// ===========================================================================
// 13. CHECKBOX — named export
// ===========================================================================

describe("Checkbox — named export", () => {
  it("exports a Checkbox component", () => {
    const source = readComponent("checkbox.tsx");
    expect(source).toMatch(/export.*\bCheckbox\b/);
  });
});

// ===========================================================================
// 14. CHECKBOX — design system tokens
// ===========================================================================

describe("Checkbox — design system tokens", () => {
  it("uses interactive-default token for checked state", () => {
    const source = readComponent("checkbox.tsx");
    expect(source).toMatch(/interactive-default/);
  });

  it("uses border-default token for unchecked border", () => {
    const source = readComponent("checkbox.tsx");
    expect(source).toMatch(/border-default/);
  });

  it("uses surface-primary token for unchecked background", () => {
    const source = readComponent("checkbox.tsx");
    expect(source).toMatch(/surface-primary/);
  });

  it("uses radius-xs or rounded-xs utility for rounded corners", () => {
    const source = readComponent("checkbox.tsx");
    // CVA+Tailwind: rounded-xs maps to --radius-xs via @theme inline
    expect(source).toMatch(/radius-xs|rounded-xs/);
  });
});

// ===========================================================================
// 15. CHECKBOX — states
// ===========================================================================

describe("Checkbox — state support", () => {
  it("supports an indeterminate state", () => {
    const source = readComponent("checkbox.tsx");
    expect(source).toMatch(/indeterminate/);
  });

  it("supports a disabled state", () => {
    const source = readComponent("checkbox.tsx");
    expect(source).toMatch(/disabled/);
  });
});

// ===========================================================================
// 16. CHECKBOX — ARIA
// ===========================================================================

describe("Checkbox — ARIA compliance", () => {
  it("uses a native checkbox input or role='checkbox'", () => {
    const source = readComponent("checkbox.tsx");
    // ARIA: native input[type=checkbox] or role="checkbox"
    expect(source).toMatch(/type\s*=\s*["']checkbox["']|role\s*=\s*["']checkbox["']/);
  });
});

// ===========================================================================
// 17. RADIO — file exists
// ===========================================================================

describe("Radio — component file exists", () => {
  it("radio.tsx exists in src/components/ui/", () => {
    expect(componentExists("radio.tsx")).toBe(true);
  });
});

// ===========================================================================
// 18. RADIO — named export
// ===========================================================================

describe("Radio — named export", () => {
  it("exports a Radio component", () => {
    const source = readComponent("radio.tsx");
    expect(source).toMatch(/export.*\bRadio\b/);
  });
});

// ===========================================================================
// 19. RADIO — design system tokens
// ===========================================================================

describe("Radio — design system tokens", () => {
  it("uses interactive-default token for selected state", () => {
    const source = readComponent("radio.tsx");
    expect(source).toMatch(/interactive-default/);
  });

  it("uses border-default token for unselected border", () => {
    const source = readComponent("radio.tsx");
    expect(source).toMatch(/border-default/);
  });

  it("uses radius-full token for circular shape", () => {
    const source = readComponent("radio.tsx");
    expect(source).toMatch(/radius-full/);
  });

  it("uses surface-primary token for unselected background", () => {
    const source = readComponent("radio.tsx");
    expect(source).toMatch(/surface-primary/);
  });
});

// ===========================================================================
// 20. RADIO — layout support
// ===========================================================================

describe("Radio — layout support", () => {
  it("supports vertical layout (default radio-group orientation)", () => {
    const source = readComponent("radio.tsx");
    // RadioGroup must support vertical stacking
    expect(source).toMatch(/vertical|flex-col|RadioGroup/);
  });

  it("supports horizontal layout", () => {
    const source = readComponent("radio.tsx");
    // RadioGroup must support horizontal layout
    expect(source).toMatch(/horizontal|flex-row|inline-flex/);
  });
});

// ===========================================================================
// 21. RADIO — states
// ===========================================================================

describe("Radio — state support", () => {
  it("supports a disabled state", () => {
    const source = readComponent("radio.tsx");
    expect(source).toMatch(/disabled/);
  });
});

// ===========================================================================
// 22. RADIO — ARIA
// ===========================================================================

describe("Radio — ARIA compliance", () => {
  it("uses a native radio input or role='radio'", () => {
    const source = readComponent("radio.tsx");
    // ARIA: native input[type=radio] or role="radio"
    expect(source).toMatch(/type\s*=\s*["']radio["']|role\s*=\s*["']radio["']/);
  });
});

// ===========================================================================
// 23. SLIDER — file exists
// ===========================================================================

describe("Slider — component file exists", () => {
  it("slider.tsx exists in src/components/ui/", () => {
    expect(componentExists("slider.tsx")).toBe(true);
  });
});

// ===========================================================================
// 24. SLIDER — named export
// ===========================================================================

describe("Slider — named export", () => {
  it("exports a Slider component", () => {
    const source = readComponent("slider.tsx");
    expect(source).toMatch(/export.*\bSlider\b/);
  });
});

// ===========================================================================
// 25. SLIDER — design system tokens
// ===========================================================================

describe("Slider — design system tokens", () => {
  it("uses surface-tertiary or neutral-5 token for track background", () => {
    const source = readComponent("slider.tsx");
    expect(source).toMatch(/surface-tertiary|neutral-5/);
  });

  it("uses interactive-default token for the filled portion", () => {
    const source = readComponent("slider.tsx");
    expect(source).toMatch(/interactive-default/);
  });

  it("uses neutral-12 or surface-primary token for thumb background", () => {
    const source = readComponent("slider.tsx");
    expect(source).toMatch(/neutral-12|surface-primary/);
  });

  it("uses elevation-raised-shadow or shadow-raised token on thumb", () => {
    const source = readComponent("slider.tsx");
    expect(source).toMatch(/elevation-raised-shadow|shadow-raised/);
  });

  it("uses radius-full token for circular thumb shape", () => {
    const source = readComponent("slider.tsx");
    expect(source).toMatch(/radius-full/);
  });
});

// ===========================================================================
// 26. SLIDER — ARIA
// ===========================================================================

describe("Slider — ARIA compliance", () => {
  it("uses a native range input or role='slider'", () => {
    const source = readComponent("slider.tsx");
    // ARIA: native input[type=range] or role="slider"
    expect(source).toMatch(/type\s*=\s*["']range["']|role\s*=\s*["']slider["']/);
  });
});
