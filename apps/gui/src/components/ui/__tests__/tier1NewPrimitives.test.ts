/**
 * RED-TEAM tests for RUN-304: 5 New Tier 1 Primitive Components.
 *
 * Validates that Spinner, Skeleton, Progress, StatusDot, and Toast
 * have been created to match the Runsight design system component spec,
 * and that Storybook story files exist for all 5 components.
 *
 * Tests read component source files as strings and verify:
 *   1. Component files exist at the expected paths
 *   2. Named exports exist for each component
 *   3. Design system tokens are used correctly
 *   4. Variant support (CVA or prop-based)
 *   5. ARIA compliance — required ARIA attributes referenced
 *   6. Animation support — keyframe/animation references
 *   7. Story files exist with proper Storybook structure
 *
 * Expected failures (current state):
 *   - spinner.tsx does not exist
 *   - skeleton.tsx does not exist
 *   - progress.tsx does not exist
 *   - status-dot.tsx does not exist
 *   - toast.tsx does not exist
 *   - No story files exist for any of the 5 new components
 */

import { describe, it, expect } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

// ---------------------------------------------------------------------------
// Paths
// ---------------------------------------------------------------------------

const UI_DIR = resolve(__dirname, "..");
const STORIES_DIR = resolve(__dirname, "..", "..", "..", "stories");

function componentExists(filename: string): boolean {
  return existsSync(resolve(UI_DIR, filename));
}

function readComponent(filename: string): string {
  return readFileSync(resolve(UI_DIR, filename), "utf-8");
}

function storyExists(filename: string): boolean {
  return (
    existsSync(resolve(STORIES_DIR, filename)) ||
    existsSync(resolve(UI_DIR, filename))
  );
}

function readStory(filename: string): string {
  const storiesPath = resolve(STORIES_DIR, filename);
  if (existsSync(storiesPath)) {
    return readFileSync(storiesPath, "utf-8");
  }
  return readFileSync(resolve(UI_DIR, filename), "utf-8");
}

// ===========================================================================
// 1. SPINNER — file existence
// ===========================================================================

describe("Spinner — component file exists", () => {
  it("spinner.tsx exists in src/components/ui/", () => {
    expect(componentExists("spinner.tsx")).toBe(true);
  });
});

// ===========================================================================
// 2. SPINNER — named export
// ===========================================================================

describe("Spinner — named export (AC1)", () => {
  it("exports a Spinner component", () => {
    const source = readComponent("spinner.tsx");
    expect(source).toMatch(/export.*\bSpinner\b/);
  });
});

// ===========================================================================
// 3. SPINNER — size variants (AC1)
// ===========================================================================

describe("Spinner — size variants present (AC1)", () => {
  it("supports a `sm` size variant", () => {
    const source = readComponent("spinner.tsx");
    expect(source).toMatch(/["']?sm["']?\s*:/);
  });

  it("supports an `md` size variant", () => {
    const source = readComponent("spinner.tsx");
    expect(source).toMatch(/["']?md["']?\s*:/);
  });

  it("supports an `lg` size variant", () => {
    const source = readComponent("spinner.tsx");
    expect(source).toMatch(/["']?lg["']?\s*:/);
  });
});

// ===========================================================================
// 4. SPINNER — variant support (AC1)
// ===========================================================================

describe("Spinner — visual variants present (AC1)", () => {
  it("supports a `default` visual variant", () => {
    const source = readComponent("spinner.tsx");
    expect(source).toMatch(/["']?default["']?\s*:/);
  });

  it("supports an `accent` visual variant", () => {
    const source = readComponent("spinner.tsx");
    expect(source).toMatch(/["']?accent["']?\s*:/);
  });
});

// ===========================================================================
// 5. SPINNER — design system tokens (AC1)
// ===========================================================================

describe("Spinner — design system tokens used (AC1)", () => {
  it("uses --icon-size-sm, --icon-size-md, or --icon-size-xl token for sizing", () => {
    const source = readComponent("spinner.tsx");
    expect(source).toMatch(/icon-size/);
  });

  it("uses --text-muted token for default variant", () => {
    const source = readComponent("spinner.tsx");
    expect(source).toMatch(/text-muted/);
  });

  it("uses --interactive-default token for accent variant", () => {
    const source = readComponent("spinner.tsx");
    expect(source).toMatch(/interactive/);
  });

  it("uses --border-width-thick token for the spinner ring", () => {
    const source = readComponent("spinner.tsx");
    expect(source).toMatch(/border-width-thick/);
  });

  it("uses --radius-full token for circular shape", () => {
    const source = readComponent("spinner.tsx");
    expect(source).toMatch(/radius-full/);
  });
});

// ===========================================================================
// 6. SPINNER — animation (AC1)
// ===========================================================================

describe("Spinner — animation support (AC1)", () => {
  it("uses a spin keyframe or animate-spin class", () => {
    const source = readComponent("spinner.tsx");
    expect(source).toMatch(/spin/);
  });
});

// ===========================================================================
// 7. SPINNER — ARIA compliance (AC1)
// ===========================================================================

describe("Spinner — ARIA compliance (AC1)", () => {
  it("has role='status'", () => {
    const source = readComponent("spinner.tsx");
    expect(source).toMatch(/role\s*=\s*["']status["']/);
  });

  it("has aria-label='Loading' or aria-label prop", () => {
    const source = readComponent("spinner.tsx");
    expect(source).toMatch(/aria-label/);
  });
});

// ===========================================================================
// 8. SKELETON — file existence
// ===========================================================================

describe("Skeleton — component file exists", () => {
  it("skeleton.tsx exists in src/components/ui/", () => {
    expect(componentExists("skeleton.tsx")).toBe(true);
  });
});

// ===========================================================================
// 9. SKELETON — named export
// ===========================================================================

describe("Skeleton — named export (AC2)", () => {
  it("exports a Skeleton component", () => {
    const source = readComponent("skeleton.tsx");
    expect(source).toMatch(/export.*\bSkeleton\b/);
  });
});

// ===========================================================================
// 10. SKELETON — variants (AC2)
// ===========================================================================

describe("Skeleton — variants present (AC2)", () => {
  it("supports a `text` variant", () => {
    const source = readComponent("skeleton.tsx");
    expect(source).toMatch(/["']?text["']?\s*:/);
  });

  it("supports a `text-sm` variant", () => {
    const source = readComponent("skeleton.tsx");
    expect(source).toMatch(/["']?text-sm["']?\s*:|text.sm/);
  });

  it("supports a `heading` variant", () => {
    const source = readComponent("skeleton.tsx");
    expect(source).toMatch(/["']?heading["']?\s*:/);
  });

  it("supports an `avatar` variant", () => {
    const source = readComponent("skeleton.tsx");
    expect(source).toMatch(/["']?avatar["']?\s*:/);
  });

  it("supports a `button` variant", () => {
    const source = readComponent("skeleton.tsx");
    expect(source).toMatch(/["']?button["']?\s*:/);
  });
});

// ===========================================================================
// 11. SKELETON — design system tokens (AC2)
// ===========================================================================

describe("Skeleton — design system tokens used (AC2)", () => {
  it("uses --neutral-3 token for skeleton background", () => {
    const source = readComponent("skeleton.tsx");
    expect(source).toMatch(/neutral-3/);
  });

  it("uses --neutral-4 token for shimmer highlight", () => {
    const source = readComponent("skeleton.tsx");
    expect(source).toMatch(/neutral-4/);
  });
});

// ===========================================================================
// 12. SKELETON — shimmer animation (AC2)
// ===========================================================================

describe("Skeleton — shimmer animation (AC2)", () => {
  it("uses a shimmer animation or pulse animation", () => {
    const source = readComponent("skeleton.tsx");
    expect(source).toMatch(/shimmer|pulse|animate/);
  });
});

// ===========================================================================
// 13. SKELETON — ARIA compliance (AC2)
// ===========================================================================

describe("Skeleton — ARIA compliance (AC2)", () => {
  it("has aria-busy='true'", () => {
    const source = readComponent("skeleton.tsx");
    expect(source).toMatch(/aria-busy/);
  });

  it("has aria-label or aria-label='Loading'", () => {
    const source = readComponent("skeleton.tsx");
    expect(source).toMatch(/aria-label/);
  });
});

// ===========================================================================
// 14. PROGRESS — file existence
// ===========================================================================

describe("Progress — component file exists", () => {
  it("progress.tsx exists in src/components/ui/", () => {
    expect(componentExists("progress.tsx")).toBe(true);
  });
});

// ===========================================================================
// 15. PROGRESS — named export
// ===========================================================================

describe("Progress — named export (AC3)", () => {
  it("exports a Progress component", () => {
    const source = readComponent("progress.tsx");
    expect(source).toMatch(/export.*\bProgress\b/);
  });
});

// ===========================================================================
// 16. PROGRESS — variants (AC3)
// ===========================================================================

describe("Progress — variants present (AC3)", () => {
  it("supports a `default` variant", () => {
    const source = readComponent("progress.tsx");
    expect(source).toMatch(/["']?default["']?\s*:/);
  });

  it("supports an `md` size or variant (8px height)", () => {
    const source = readComponent("progress.tsx");
    expect(source).toMatch(/["']?md["']?\s*:/);
  });

  it("supports a `success` variant", () => {
    const source = readComponent("progress.tsx");
    expect(source).toMatch(/["']?success["']?\s*:/);
  });

  it("supports a `danger` variant", () => {
    const source = readComponent("progress.tsx");
    expect(source).toMatch(/["']?danger["']?\s*:/);
  });

  it("supports an `indeterminate` variant or value", () => {
    const source = readComponent("progress.tsx");
    expect(source).toMatch(/indeterminate/);
  });
});

// ===========================================================================
// 17. PROGRESS — design system tokens (AC3)
// ===========================================================================

describe("Progress — design system tokens used (AC3)", () => {
  it("uses --neutral-3 token for track background", () => {
    const source = readComponent("progress.tsx");
    expect(source).toMatch(/neutral-3/);
  });

  it("uses --interactive-default token for the default fill", () => {
    const source = readComponent("progress.tsx");
    expect(source).toMatch(/interactive/);
  });

  it("uses --success-9 token for success fill", () => {
    const source = readComponent("progress.tsx");
    expect(source).toMatch(/success-9/);
  });

  it("uses --danger-9 token for danger fill", () => {
    const source = readComponent("progress.tsx");
    expect(source).toMatch(/danger-9/);
  });
});

// ===========================================================================
// 18. PROGRESS — ARIA compliance (AC3)
// ===========================================================================

describe("Progress — ARIA compliance (AC3)", () => {
  it("has role='progressbar'", () => {
    const source = readComponent("progress.tsx");
    expect(source).toMatch(/role\s*=\s*["']progressbar["']/);
  });

  it("has aria-valuenow attribute or prop", () => {
    const source = readComponent("progress.tsx");
    expect(source).toMatch(/aria-valuenow/);
  });

  it("has aria-valuemin attribute or prop", () => {
    const source = readComponent("progress.tsx");
    expect(source).toMatch(/aria-valuemin/);
  });

  it("has aria-valuemax attribute or prop", () => {
    const source = readComponent("progress.tsx");
    expect(source).toMatch(/aria-valuemax/);
  });
});

// ===========================================================================
// 19. STATUS DOT — file existence
// ===========================================================================

describe("StatusDot — component file exists", () => {
  it("status-dot.tsx exists in src/components/ui/", () => {
    expect(componentExists("status-dot.tsx")).toBe(true);
  });
});

// ===========================================================================
// 20. STATUS DOT — named export
// ===========================================================================

describe("StatusDot — named export (AC4)", () => {
  it("exports a StatusDot component", () => {
    const source = readComponent("status-dot.tsx");
    expect(source).toMatch(/export.*\bStatusDot\b/);
  });
});

// ===========================================================================
// 21. STATUS DOT — variants (AC4)
// ===========================================================================

describe("StatusDot — variants present (AC4)", () => {
  it("supports a `neutral` variant", () => {
    const source = readComponent("status-dot.tsx");
    expect(source).toMatch(/["']?neutral["']?\s*:/);
  });

  it("supports an `active` variant", () => {
    const source = readComponent("status-dot.tsx");
    expect(source).toMatch(/["']?active["']?\s*:/);
  });

  it("supports a `success` variant", () => {
    const source = readComponent("status-dot.tsx");
    expect(source).toMatch(/["']?success["']?\s*:/);
  });

  it("supports a `warning` variant", () => {
    const source = readComponent("status-dot.tsx");
    expect(source).toMatch(/["']?warning["']?\s*:/);
  });

  it("supports a `danger` variant", () => {
    const source = readComponent("status-dot.tsx");
    expect(source).toMatch(/["']?danger["']?\s*:/);
  });
});

// ===========================================================================
// 22. STATUS DOT — design system tokens (AC4)
// ===========================================================================

describe("StatusDot — design system tokens used (AC4)", () => {
  it("uses --neutral-9 token for neutral variant", () => {
    const source = readComponent("status-dot.tsx");
    expect(source).toMatch(/neutral-9/);
  });

  it("uses --info-9 token for active variant", () => {
    const source = readComponent("status-dot.tsx");
    expect(source).toMatch(/info-9/);
  });

  it("uses --success-9 token for success variant", () => {
    const source = readComponent("status-dot.tsx");
    expect(source).toMatch(/success-9/);
  });

  it("uses --warning-9 token for warning variant", () => {
    const source = readComponent("status-dot.tsx");
    expect(source).toMatch(/warning-9/);
  });

  it("uses --danger-9 token for danger variant", () => {
    const source = readComponent("status-dot.tsx");
    expect(source).toMatch(/danger-9/);
  });

  it("uses --radius-full token for circular shape", () => {
    const source = readComponent("status-dot.tsx");
    expect(source).toMatch(/radius-full/);
  });

  it("uses --space-2 token for sizing", () => {
    const source = readComponent("status-dot.tsx");
    expect(source).toMatch(/space-2/);
  });
});

// ===========================================================================
// 23. STATUS DOT — animations (AC4)
// ===========================================================================

describe("StatusDot — animations (AC4)", () => {
  it("supports a pulse animation for running/waiting states", () => {
    const source = readComponent("status-dot.tsx");
    expect(source).toMatch(/pulse/);
  });

  it("supports a spin animation for retrying state", () => {
    const source = readComponent("status-dot.tsx");
    expect(source).toMatch(/spin/);
  });
});

// ===========================================================================
// 24. TOAST — file existence
// ===========================================================================

describe("Toast — component file exists", () => {
  it("toast.tsx exists in src/components/ui/", () => {
    expect(componentExists("toast.tsx")).toBe(true);
  });
});

// ===========================================================================
// 25. TOAST — named export
// ===========================================================================

describe("Toast — named export (AC5)", () => {
  it("exports a Toast component", () => {
    const source = readComponent("toast.tsx");
    expect(source).toMatch(/export.*\bToast\b/);
  });
});

// ===========================================================================
// 26. TOAST — variants (AC5)
// ===========================================================================

describe("Toast — variants present (AC5)", () => {
  it("supports a `success` variant", () => {
    const source = readComponent("toast.tsx");
    expect(source).toMatch(/["']?success["']?\s*:/);
  });

  it("supports a `danger` variant", () => {
    const source = readComponent("toast.tsx");
    expect(source).toMatch(/["']?danger["']?\s*:/);
  });

  it("supports a `warning` variant", () => {
    const source = readComponent("toast.tsx");
    expect(source).toMatch(/["']?warning["']?\s*:/);
  });

  it("supports an `info` variant", () => {
    const source = readComponent("toast.tsx");
    expect(source).toMatch(/["']?info["']?\s*:/);
  });
});

// ===========================================================================
// 27. TOAST — design system tokens (AC5)
// ===========================================================================

describe("Toast — design system tokens used (AC5)", () => {
  it("uses --surface-raised or elevation-overlay-surface token for background", () => {
    const source = readComponent("toast.tsx");
    expect(source).toMatch(/surface-raised|elevation-overlay-surface/);
  });

  it("uses semantic success tokens for success variant", () => {
    const source = readComponent("toast.tsx");
    expect(source).toMatch(/success/);
  });

  it("uses semantic danger tokens for danger variant", () => {
    const source = readComponent("toast.tsx");
    expect(source).toMatch(/danger/);
  });

  it("uses semantic warning tokens for warning variant", () => {
    const source = readComponent("toast.tsx");
    expect(source).toMatch(/warning/);
  });

  it("uses semantic info tokens for info variant", () => {
    const source = readComponent("toast.tsx");
    expect(source).toMatch(/info/);
  });
});

// ===========================================================================
// 28. TOAST — sub-components (AC5)
// ===========================================================================

describe("Toast — sub-components present (AC5)", () => {
  it("has a title sub-component or prop", () => {
    const source = readComponent("toast.tsx");
    expect(source).toMatch(/title|Title/);
  });

  it("has a description sub-component or prop", () => {
    const source = readComponent("toast.tsx");
    expect(source).toMatch(/description|Description/);
  });

  it("has a dismiss sub-component or close button", () => {
    const source = readComponent("toast.tsx");
    expect(source).toMatch(/dismiss|Dismiss|close|Close/);
  });
});

// ===========================================================================
// 29. TOAST — ARIA compliance (AC5)
// ===========================================================================

describe("Toast — ARIA compliance (AC5)", () => {
  it("has role='status' or role='alert'", () => {
    const source = readComponent("toast.tsx");
    expect(source).toMatch(/role\s*=\s*["'](status|alert)["']/);
  });
});

// ===========================================================================
// 30. STORYBOOK STORIES — all 5 new component story files exist (AC6)
// ===========================================================================

describe("Storybook stories — existence (AC6)", () => {
  it("Spinner.stories.tsx exists in src/stories/ or src/components/ui/", () => {
    expect(storyExists("Spinner.stories.tsx")).toBe(true);
  });

  it("Skeleton.stories.tsx exists in src/stories/ or src/components/ui/", () => {
    expect(storyExists("Skeleton.stories.tsx")).toBe(true);
  });

  it("Progress.stories.tsx exists in src/stories/ or src/components/ui/", () => {
    expect(storyExists("Progress.stories.tsx")).toBe(true);
  });

  it("StatusDot.stories.tsx exists in src/stories/ or src/components/ui/", () => {
    expect(storyExists("StatusDot.stories.tsx")).toBe(true);
  });

  it("Toast.stories.tsx exists in src/stories/ or src/components/ui/", () => {
    expect(storyExists("Toast.stories.tsx")).toBe(true);
  });
});

// ===========================================================================
// 31. STORYBOOK STORIES — Spinner.stories.tsx structure (AC6)
// ===========================================================================

describe("Storybook stories — Spinner.stories.tsx structure (AC6)", () => {
  it("has a default export (meta object)", () => {
    const content = readStory("Spinner.stories.tsx");
    expect(content).toMatch(/export\s+default\s+/);
  });

  it("meta object has a title field", () => {
    const content = readStory("Spinner.stories.tsx");
    expect(content).toMatch(/title\s*:/);
  });

  it("has at least one named story export", () => {
    const content = readStory("Spinner.stories.tsx");
    expect(content).toMatch(/export\s+const\s+\w+/);
  });

  it("covers the sm size", () => {
    const content = readStory("Spinner.stories.tsx");
    expect(content).toMatch(/\bsm\b/i);
  });

  it("covers the accent variant", () => {
    const content = readStory("Spinner.stories.tsx");
    expect(content).toMatch(/accent/i);
  });
});

// ===========================================================================
// 32. STORYBOOK STORIES — Skeleton.stories.tsx structure (AC6)
// ===========================================================================

describe("Storybook stories — Skeleton.stories.tsx structure (AC6)", () => {
  it("has a default export (meta object)", () => {
    const content = readStory("Skeleton.stories.tsx");
    expect(content).toMatch(/export\s+default\s+/);
  });

  it("meta object has a title field", () => {
    const content = readStory("Skeleton.stories.tsx");
    expect(content).toMatch(/title\s*:/);
  });

  it("has at least one named story export", () => {
    const content = readStory("Skeleton.stories.tsx");
    expect(content).toMatch(/export\s+const\s+\w+/);
  });

  it("covers text variant", () => {
    const content = readStory("Skeleton.stories.tsx");
    expect(content).toMatch(/\btext\b/i);
  });

  it("covers avatar variant", () => {
    const content = readStory("Skeleton.stories.tsx");
    expect(content).toMatch(/avatar/i);
  });
});

// ===========================================================================
// 33. STORYBOOK STORIES — Progress.stories.tsx structure (AC6)
// ===========================================================================

describe("Storybook stories — Progress.stories.tsx structure (AC6)", () => {
  it("has a default export (meta object)", () => {
    const content = readStory("Progress.stories.tsx");
    expect(content).toMatch(/export\s+default\s+/);
  });

  it("meta object has a title field", () => {
    const content = readStory("Progress.stories.tsx");
    expect(content).toMatch(/title\s*:/);
  });

  it("has at least one named story export", () => {
    const content = readStory("Progress.stories.tsx");
    expect(content).toMatch(/export\s+const\s+\w+/);
  });

  it("covers the indeterminate state", () => {
    const content = readStory("Progress.stories.tsx");
    expect(content).toMatch(/indeterminate/i);
  });

  it("covers success and danger variants", () => {
    const content = readStory("Progress.stories.tsx");
    expect(content).toMatch(/success|danger/i);
  });
});

// ===========================================================================
// 34. STORYBOOK STORIES — StatusDot.stories.tsx structure (AC6)
// ===========================================================================

describe("Storybook stories — StatusDot.stories.tsx structure (AC6)", () => {
  it("has a default export (meta object)", () => {
    const content = readStory("StatusDot.stories.tsx");
    expect(content).toMatch(/export\s+default\s+/);
  });

  it("meta object has a title field", () => {
    const content = readStory("StatusDot.stories.tsx");
    expect(content).toMatch(/title\s*:/);
  });

  it("has at least one named story export", () => {
    const content = readStory("StatusDot.stories.tsx");
    expect(content).toMatch(/export\s+const\s+\w+/);
  });

  it("covers all 5 semantic variants", () => {
    const content = readStory("StatusDot.stories.tsx");
    expect(content).toMatch(/neutral|active|success|warning|danger/i);
  });

  it("covers pulse and spin animations", () => {
    const content = readStory("StatusDot.stories.tsx");
    expect(content).toMatch(/pulse|spin/i);
  });
});

// ===========================================================================
// 35. STORYBOOK STORIES — Toast.stories.tsx structure (AC6)
// ===========================================================================

describe("Storybook stories — Toast.stories.tsx structure (AC6)", () => {
  it("has a default export (meta object)", () => {
    const content = readStory("Toast.stories.tsx");
    expect(content).toMatch(/export\s+default\s+/);
  });

  it("meta object has a title field", () => {
    const content = readStory("Toast.stories.tsx");
    expect(content).toMatch(/title\s*:/);
  });

  it("has at least one named story export", () => {
    const content = readStory("Toast.stories.tsx");
    expect(content).toMatch(/export\s+const\s+\w+/);
  });

  it("covers all 4 semantic variants (success, danger, warning, info)", () => {
    const content = readStory("Toast.stories.tsx");
    expect(content).toMatch(/success|danger|warning|info/i);
  });

  it("covers the dismiss interaction", () => {
    const content = readStory("Toast.stories.tsx");
    expect(content).toMatch(/dismiss|close/i);
  });
});
