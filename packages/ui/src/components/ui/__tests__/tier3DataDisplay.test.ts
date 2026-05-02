/**
 * Tier 3 data display component coverage.
 *
 * Validates that Table and Card have been updated to use the Runsight design
 * system tokens, and that StatCard and CodeBlock have been created
 * to match the design system component spec.
 *
 * Tests read component source files as strings and verify:
 *   1. Existing components (table, card): required design system tokens present
 *   2. New components (stat-card, code-block): file exists, exports, tokens
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
// 1. TABLE — header background token
// ===========================================================================

describe("Table — surface-secondary token on header", () => {
  it("uses surface-secondary or surface-primary token for table header background", () => {
    const source = readComponent("table.tsx");
    // Spec: header background is --surface-secondary (or surface-primary for sticky header)
    expect(source).toMatch(/surface-secondary|surface-primary/);
  });
});

// ===========================================================================
// 2. TABLE — header text color token
// ===========================================================================

describe("Table — text-secondary or text-muted token on header cells", () => {
  it("uses text-secondary or text-muted token for header cell text color", () => {
    const source = readComponent("table.tsx");
    // Spec: header cell text uses --text-secondary or --text-muted (muted is the migrated equivalent)
    expect(source).toMatch(/text-secondary|text-muted/);
  });
});

// ===========================================================================
// 3. TABLE — header font-size token
// ===========================================================================

describe("Table — font-size-xs or text-2xs token on header cells", () => {
  it("uses font-size-xs or text-2xs token for header cell font size", () => {
    const source = readComponent("table.tsx");
    // Spec: header cells use --font-size-xs; text-2xs is the Tailwind CVA equivalent
    expect(source).toMatch(/font-size-xs|text-2xs/);
  });
});

// ===========================================================================
// 4. TABLE — header uppercase text transform
// ===========================================================================

describe("Table — uppercase text transform on header cells", () => {
  it("applies uppercase text transform to header cells", () => {
    const source = readComponent("table.tsx");
    // Spec: header cell labels are uppercase
    // Current state: no uppercase applied
    expect(source).toMatch(/uppercase/);
  });
});

// ===========================================================================
// 5. TABLE — row hover token
// ===========================================================================

describe("Table — surface-hover token on row hover", () => {
  it("uses surface-hover token for row hover state", () => {
    const source = readComponent("table.tsx");
    // Spec: row hover uses --surface-hover
    // Current state: TableRow uses hover:bg-surface-tertiary/50 (wrong token)
    expect(source).toMatch(/surface-hover/);
  });
});

// ===========================================================================
// 6. TABLE — border token
// ===========================================================================

describe("Table — border-subtle token for borders", () => {
  it("uses border-subtle token for table borders", () => {
    const source = readComponent("table.tsx");
    // Spec: borders use --border-subtle
    // Current state: uses border-b (hardcoded Tailwind border, no DS token)
    expect(source).toMatch(/border-subtle/);
  });
});

// ===========================================================================
// 7. TABLE — row height density token
// ===========================================================================

describe("Table — density-row-height token for row height", () => {
  it("uses density-row-height or density token for row height", () => {
    const source = readComponent("table.tsx");
    // Spec: row height uses --density-row-height DS token
    // Current state: TableHead uses h-10 (hardcoded, no DS token)
    expect(source).toMatch(/density-row-height|density/);
  });
});

// ===========================================================================
// 8. TABLE — mono font token
// ===========================================================================

describe("Table — font-mono token for mono values", () => {
  it("uses font-mono design system token for monospaced values", () => {
    const source = readComponent("table.tsx");
    // Spec: mono values use --font-mono DS token
    // Current state: no font-mono token reference
    expect(source).toMatch(/font-mono/);
  });
});

// ===========================================================================
// 9. CARD — border-subtle token
// ===========================================================================

describe("Card — border-subtle token for border", () => {
  it("uses border-subtle token for card border", () => {
    const source = readComponent("card.tsx");
    // Spec: card border uses --border-subtle
    // Current state: uses ring-1 ring-foreground/10 (not the DS border-subtle token)
    expect(source).toMatch(/border-subtle/);
  });
});

// ===========================================================================
// 10. CARD — radius-lg token
// ===========================================================================

describe("Card — radius-lg or rounded-lg token for border radius", () => {
  it("uses radius-lg or rounded-lg for card border radius", () => {
    const source = readComponent("card.tsx");
    // Spec: radius uses --radius-lg DS token; rounded-lg is the Tailwind CVA equivalent
    expect(source).toMatch(/radius-lg|rounded-lg/);
  });
});

// ===========================================================================
// 11. CARD — space-4 token for padding
// ===========================================================================

describe("Card — space-4 or p-4 token for padding", () => {
  it("uses space-4 or p-4 for card padding", () => {
    const source = readComponent("card.tsx");
    // Spec: padding uses --space-4 DS token; p-4 is the Tailwind CVA equivalent
    expect(source).toMatch(/space-4|p-4/);
  });
});

// ===========================================================================
// 12. CARD — text-heading token for header
// ===========================================================================

describe("Card — text-heading token for header text", () => {
  it("uses text-heading token for card header text", () => {
    const source = readComponent("card.tsx");
    // Spec: header text uses --text-heading DS token
    // Current state: CardTitle uses font-medium text-base (no DS text-heading token)
    expect(source).toMatch(/text-heading/);
  });
});

// ===========================================================================
// 13. STAT CARD — file exists
// ===========================================================================

describe("StatCard — component file exists", () => {
  it("stat-card.tsx exists in src/components/ui/", () => {
    expect(componentExists("stat-card.tsx")).toBe(true);
  });
});

// ===========================================================================
// 14. STAT CARD — named export
// ===========================================================================

describe("StatCard — named export", () => {
  it("exports a StatCard component", () => {
    const source = readComponent("stat-card.tsx");
    expect(source).toMatch(/export.*\bStatCard\b/);
  });
});

// ===========================================================================
// 15. STAT CARD — design system tokens
// ===========================================================================

describe("StatCard — design system tokens", () => {
  it("uses text-secondary or text-muted token for label", () => {
    const source = readComponent("stat-card.tsx");
    // Spec: label text color uses --text-secondary or --text-muted (muted is the CVA equivalent)
    expect(source).toMatch(/text-secondary|text-muted/);
  });

  it("uses font-size-xs token for label font size", () => {
    const source = readComponent("stat-card.tsx");
    // Spec: label font size uses --font-size-xs
    expect(source).toMatch(/font-size-xs/);
  });

  it("uses font-mono token for value display", () => {
    const source = readComponent("stat-card.tsx");
    // Spec: value uses --font-mono for monospaced rendering
    expect(source).toMatch(/font-mono/);
  });

  it("uses font-size-2xl or large text class for value font size", () => {
    const source = readComponent("stat-card.tsx");
    // Spec: value font size uses --font-size-2xl or larger; text-3xl is the CVA equivalent
    expect(source).toMatch(/font-size-2xl|text-2xl|text-3xl/);
  });

  it("uses text-heading token for value text color", () => {
    const source = readComponent("stat-card.tsx");
    // Spec: value text color uses --text-heading
    expect(source).toMatch(/text-heading/);
  });
});

// ===========================================================================
// 16. STAT CARD — category stripe
// ===========================================================================

describe("StatCard — top 3px category stripe", () => {
  it("renders a top category stripe (3px border-top or decorative bar)", () => {
    const source = readComponent("stat-card.tsx");
    // Spec: top 3px category stripe — check for stripe indicator
    expect(source).toMatch(/stripe|border-t|border-top|inset-x/);
  });
});

// ===========================================================================
// 17. STAT CARD — uppercase label
// ===========================================================================

describe("StatCard — uppercase label text transform", () => {
  it("applies uppercase text transform to the label", () => {
    const source = readComponent("stat-card.tsx");
    // Spec: label is uppercase
    expect(source).toMatch(/uppercase/);
  });
});

// ===========================================================================
// 18. STAT CARD — optional delta badge
// ===========================================================================

describe("StatCard — optional delta badge support", () => {
  it("supports an optional delta/change indicator prop", () => {
    const source = readComponent("stat-card.tsx");
    // Spec: optional delta badge (positive/negative change indicator)
    expect(source).toMatch(/delta|Delta|change|trend/i);
  });
});

// ===========================================================================
// 19. CODE BLOCK — file exists
// ===========================================================================

describe("CodeBlock — component file exists", () => {
  it("code-block.tsx exists in src/components/ui/", () => {
    expect(componentExists("code-block.tsx")).toBe(true);
  });
});

// ===========================================================================
// 20. CODE BLOCK — named export
// ===========================================================================

describe("CodeBlock — named export", () => {
  it("exports a CodeBlock component", () => {
    const source = readComponent("code-block.tsx");
    expect(source).toMatch(/export.*\bCodeBlock\b/);
  });
});

// ===========================================================================
// 21. CODE BLOCK — design system tokens
// ===========================================================================

describe("CodeBlock — design system tokens", () => {
  it("uses neutral-2 or surface-primary token for background", () => {
    const source = readComponent("code-block.tsx");
    // Spec: background uses --neutral-2; bg-surface-primary is the CVA equivalent
    expect(source).toMatch(/neutral-2|surface-primary/);
  });

  it("uses font-mono token for font family", () => {
    const source = readComponent("code-block.tsx");
    // Spec: font uses --font-mono
    expect(source).toMatch(/font-mono/);
  });

  it("uses font-size-sm or text-sm token for font size", () => {
    const source = readComponent("code-block.tsx");
    // Spec: font size uses --font-size-sm; text-sm is the Tailwind CVA equivalent
    expect(source).toMatch(/font-size-sm|text-sm/);
  });

  it("uses syntax-key token for keyword highlighting", () => {
    const source = readComponent("code-block.tsx");
    // Spec: keyword syntax color uses --syntax-key
    expect(source).toMatch(/syntax-key/);
  });

  it("uses syntax-string token for string highlighting", () => {
    const source = readComponent("code-block.tsx");
    // Spec: string syntax color uses --syntax-string
    expect(source).toMatch(/syntax-string/);
  });

  it("uses syntax-value token for value highlighting", () => {
    const source = readComponent("code-block.tsx");
    // Spec: value syntax color uses --syntax-value
    expect(source).toMatch(/syntax-value/);
  });
});

// ===========================================================================
// 22. CODE BLOCK — copy button
// ===========================================================================

describe("CodeBlock — copy button", () => {
  it("renders a copy button", () => {
    const source = readComponent("code-block.tsx");
    // Spec: copy button for clipboard interaction
    expect(source).toMatch(/copy|Copy|clipboard|Clipboard/i);
  });
});
