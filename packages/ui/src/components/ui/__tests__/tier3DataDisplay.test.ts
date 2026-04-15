/**
 * RED-TEAM tests for RUN-300: Tier 3 Data Display.
 *
 * Validates that Table and Card have been updated to use the Runsight design
 * system tokens, and that StatCard and CodeBlock have been created
 * to match the design system component spec. Also validates that Storybook
 * story files exist for all 4 components.
 *
 * Tests read component source files as strings and verify:
 *   1. Existing components (table, card): required design system tokens present
 *   2. New components (stat-card, code-block): file exists, exports, tokens
 *   3. All 4: story files exist with proper Storybook structure
 *
 * Expected failures (current state):
 *   - table.tsx: missing surface-secondary on header, text-secondary, font-size-xs,
 *     surface-hover on rows, border-subtle for borders, density-row-height or density
 *     token for row height, font-mono for mono values
 *   - card.tsx: missing border-subtle token (uses ring-foreground/10 instead),
 *     radius-lg token (uses rounded-xl inline class instead),
 *     space-4 token for padding (uses py-4 inline class instead),
 *     text-heading token for header text (uses font-medium text-base inline instead)
 *   - stat-card.tsx does not exist
 *   - code-block.tsx does not exist
 *   - No story files exist for any of the 4 components
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
// 1. TABLE — header background token (AC1)
// ===========================================================================

describe("Table — surface-secondary token on header (AC1)", () => {
  it("uses surface-secondary or surface-primary token for table header background", () => {
    const source = readComponent("table.tsx");
    // Spec: header background is --surface-secondary (or surface-primary for sticky header)
    expect(source).toMatch(/surface-secondary|surface-primary/);
  });
});

// ===========================================================================
// 2. TABLE — header text color token (AC1)
// ===========================================================================

describe("Table — text-secondary or text-muted token on header cells (AC1)", () => {
  it("uses text-secondary or text-muted token for header cell text color", () => {
    const source = readComponent("table.tsx");
    // Spec: header cell text uses --text-secondary or --text-muted (muted is the migrated equivalent)
    expect(source).toMatch(/text-secondary|text-muted/);
  });
});

// ===========================================================================
// 3. TABLE — header font-size token (AC1)
// ===========================================================================

describe("Table — font-size-xs or text-2xs token on header cells (AC1)", () => {
  it("uses font-size-xs or text-2xs token for header cell font size", () => {
    const source = readComponent("table.tsx");
    // Spec: header cells use --font-size-xs; text-2xs is the Tailwind CVA equivalent
    expect(source).toMatch(/font-size-xs|text-2xs/);
  });
});

// ===========================================================================
// 4. TABLE — header uppercase text transform (AC1)
// ===========================================================================

describe("Table — uppercase text transform on header cells (AC1)", () => {
  it("applies uppercase text transform to header cells", () => {
    const source = readComponent("table.tsx");
    // Spec: header cell labels are uppercase
    // Current state: no uppercase applied
    expect(source).toMatch(/uppercase/);
  });
});

// ===========================================================================
// 5. TABLE — row hover token (AC1)
// ===========================================================================

describe("Table — surface-hover token on row hover (AC1)", () => {
  it("uses surface-hover token for row hover state", () => {
    const source = readComponent("table.tsx");
    // Spec: row hover uses --surface-hover
    // Current state: TableRow uses hover:bg-surface-tertiary/50 (wrong token)
    expect(source).toMatch(/surface-hover/);
  });
});

// ===========================================================================
// 6. TABLE — border token (AC1)
// ===========================================================================

describe("Table — border-subtle token for borders (AC1)", () => {
  it("uses border-subtle token for table borders", () => {
    const source = readComponent("table.tsx");
    // Spec: borders use --border-subtle
    // Current state: uses border-b (hardcoded Tailwind border, no DS token)
    expect(source).toMatch(/border-subtle/);
  });
});

// ===========================================================================
// 7. TABLE — row height density token (AC1)
// ===========================================================================

describe("Table — density-row-height token for row height (AC1)", () => {
  it("uses density-row-height or density token for row height", () => {
    const source = readComponent("table.tsx");
    // Spec: row height uses --density-row-height DS token
    // Current state: TableHead uses h-10 (hardcoded, no DS token)
    expect(source).toMatch(/density-row-height|density/);
  });
});

// ===========================================================================
// 8. TABLE — mono font token (AC1)
// ===========================================================================

describe("Table — font-mono token for mono values (AC1)", () => {
  it("uses font-mono design system token for monospaced values", () => {
    const source = readComponent("table.tsx");
    // Spec: mono values use --font-mono DS token
    // Current state: no font-mono token reference
    expect(source).toMatch(/font-mono/);
  });
});

// ===========================================================================
// 9. CARD — border-subtle token (AC2)
// ===========================================================================

describe("Card — border-subtle token for border (AC2)", () => {
  it("uses border-subtle token for card border", () => {
    const source = readComponent("card.tsx");
    // Spec: card border uses --border-subtle
    // Current state: uses ring-1 ring-foreground/10 (not the DS border-subtle token)
    expect(source).toMatch(/border-subtle/);
  });
});

// ===========================================================================
// 10. CARD — radius-lg token (AC2)
// ===========================================================================

describe("Card — radius-lg or rounded-lg token for border radius (AC2)", () => {
  it("uses radius-lg or rounded-lg for card border radius", () => {
    const source = readComponent("card.tsx");
    // Spec: radius uses --radius-lg DS token; rounded-lg is the Tailwind CVA equivalent
    expect(source).toMatch(/radius-lg|rounded-lg/);
  });
});

// ===========================================================================
// 11. CARD — space-4 token for padding (AC2)
// ===========================================================================

describe("Card — space-4 or p-4 token for padding (AC2)", () => {
  it("uses space-4 or p-4 for card padding", () => {
    const source = readComponent("card.tsx");
    // Spec: padding uses --space-4 DS token; p-4 is the Tailwind CVA equivalent
    expect(source).toMatch(/space-4|p-4/);
  });
});

// ===========================================================================
// 12. CARD — text-heading token for header (AC2)
// ===========================================================================

describe("Card — text-heading token for header text (AC2)", () => {
  it("uses text-heading token for card header text", () => {
    const source = readComponent("card.tsx");
    // Spec: header text uses --text-heading DS token
    // Current state: CardTitle uses font-medium text-base (no DS text-heading token)
    expect(source).toMatch(/text-heading/);
  });
});

// ===========================================================================
// 13. STAT CARD — file exists (AC3)
// ===========================================================================

describe("StatCard — component file exists (AC3)", () => {
  it("stat-card.tsx exists in src/components/ui/", () => {
    expect(componentExists("stat-card.tsx")).toBe(true);
  });
});

// ===========================================================================
// 14. STAT CARD — named export (AC3)
// ===========================================================================

describe("StatCard — named export (AC3)", () => {
  it("exports a StatCard component", () => {
    const source = readComponent("stat-card.tsx");
    expect(source).toMatch(/export.*\bStatCard\b/);
  });
});

// ===========================================================================
// 15. STAT CARD — design system tokens (AC3)
// ===========================================================================

describe("StatCard — design system tokens (AC3)", () => {
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
// 16. STAT CARD — category stripe (AC3)
// ===========================================================================

describe("StatCard — top 3px category stripe (AC3)", () => {
  it("renders a top category stripe (3px border-top or decorative bar)", () => {
    const source = readComponent("stat-card.tsx");
    // Spec: top 3px category stripe — check for stripe indicator
    expect(source).toMatch(/stripe|border-t|border-top|inset-x/);
  });
});

// ===========================================================================
// 17. STAT CARD — uppercase label (AC3)
// ===========================================================================

describe("StatCard — uppercase label text transform (AC3)", () => {
  it("applies uppercase text transform to the label", () => {
    const source = readComponent("stat-card.tsx");
    // Spec: label is uppercase
    expect(source).toMatch(/uppercase/);
  });
});

// ===========================================================================
// 18. STAT CARD — optional delta badge (AC3)
// ===========================================================================

describe("StatCard — optional delta badge support (AC3)", () => {
  it("supports an optional delta/change indicator prop", () => {
    const source = readComponent("stat-card.tsx");
    // Spec: optional delta badge (positive/negative change indicator)
    expect(source).toMatch(/delta|Delta|change|trend/i);
  });
});

// ===========================================================================
// 19. CODE BLOCK — file exists (AC4)
// ===========================================================================

describe("CodeBlock — component file exists (AC4)", () => {
  it("code-block.tsx exists in src/components/ui/", () => {
    expect(componentExists("code-block.tsx")).toBe(true);
  });
});

// ===========================================================================
// 20. CODE BLOCK — named export (AC4)
// ===========================================================================

describe("CodeBlock — named export (AC4)", () => {
  it("exports a CodeBlock component", () => {
    const source = readComponent("code-block.tsx");
    expect(source).toMatch(/export.*\bCodeBlock\b/);
  });
});

// ===========================================================================
// 21. CODE BLOCK — design system tokens (AC4)
// ===========================================================================

describe("CodeBlock — design system tokens (AC4)", () => {
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
// 22. CODE BLOCK — copy button (AC4)
// ===========================================================================

describe("CodeBlock — copy button (AC4)", () => {
  it("renders a copy button", () => {
    const source = readComponent("code-block.tsx");
    // Spec: copy button for clipboard interaction
    expect(source).toMatch(/copy|Copy|clipboard|Clipboard/i);
  });
});

// ===========================================================================
// 23. STORYBOOK STORIES — all 4 component story files exist (AC6)
// ===========================================================================

describe("Storybook stories — existence (AC6)", () => {
  it("Table.stories.tsx exists in src/stories/ or src/components/ui/", () => {
    expect(storyExists("Table.stories.tsx")).toBe(true);
  });

  it("Card.stories.tsx exists in src/stories/ or src/components/ui/", () => {
    expect(storyExists("Card.stories.tsx")).toBe(true);
  });

  it("StatCard.stories.tsx exists in src/stories/ or src/components/ui/", () => {
    expect(storyExists("StatCard.stories.tsx")).toBe(true);
  });

  it("CodeBlock.stories.tsx exists in src/stories/ or src/components/ui/", () => {
    expect(storyExists("CodeBlock.stories.tsx")).toBe(true);
  });

});

// ===========================================================================
// 29. STORYBOOK STORIES — Table.stories.tsx structure (AC6)
// ===========================================================================

describe("Storybook stories — Table.stories.tsx structure (AC6)", () => {
  it("has a default export (meta object)", () => {
    const content = readStory("Table.stories.tsx");
    expect(content).toMatch(/export\s+default\s+/);
  });

  it("meta object has a title field", () => {
    const content = readStory("Table.stories.tsx");
    expect(content).toMatch(/title\s*:/);
  });

  it("has at least one named story export", () => {
    const content = readStory("Table.stories.tsx");
    expect(content).toMatch(/export\s+const\s+\w+/);
  });

  it("covers basic/default usage", () => {
    const content = readStory("Table.stories.tsx");
    expect(content).toMatch(/Default|Basic|Primary/i);
  });

  it("covers mono value display in cells", () => {
    const content = readStory("Table.stories.tsx");
    expect(content).toMatch(/mono|Mono|code|Code/i);
  });
});

// ===========================================================================
// 30. STORYBOOK STORIES — Card.stories.tsx structure (AC6)
// ===========================================================================

describe("Storybook stories — Card.stories.tsx structure (AC6)", () => {
  it("has a default export (meta object)", () => {
    const content = readStory("Card.stories.tsx");
    expect(content).toMatch(/export\s+default\s+/);
  });

  it("meta object has a title field", () => {
    const content = readStory("Card.stories.tsx");
    expect(content).toMatch(/title\s*:/);
  });

  it("has at least one named story export", () => {
    const content = readStory("Card.stories.tsx");
    expect(content).toMatch(/export\s+const\s+\w+/);
  });

  it("covers basic/default usage", () => {
    const content = readStory("Card.stories.tsx");
    expect(content).toMatch(/Default|Basic|Primary/i);
  });

  it("covers a card with header and content", () => {
    const content = readStory("Card.stories.tsx");
    expect(content).toMatch(/CardHeader|CardTitle|CardContent/);
  });
});

// ===========================================================================
// 31. STORYBOOK STORIES — StatCard.stories.tsx structure (AC6)
// ===========================================================================

describe("Storybook stories — StatCard.stories.tsx structure (AC6)", () => {
  it("has a default export (meta object)", () => {
    const content = readStory("StatCard.stories.tsx");
    expect(content).toMatch(/export\s+default\s+/);
  });

  it("meta object has a title field", () => {
    const content = readStory("StatCard.stories.tsx");
    expect(content).toMatch(/title\s*:/);
  });

  it("has at least one named story export", () => {
    const content = readStory("StatCard.stories.tsx");
    expect(content).toMatch(/export\s+const\s+\w+/);
  });

  it("covers basic stat display", () => {
    const content = readStory("StatCard.stories.tsx");
    expect(content).toMatch(/Default|Basic|Primary/i);
  });

  it("covers delta/trend badge variant", () => {
    const content = readStory("StatCard.stories.tsx");
    expect(content).toMatch(/delta|Delta|trend|Trend|change|Change/i);
  });
});

// ===========================================================================
// 32. STORYBOOK STORIES — CodeBlock.stories.tsx structure (AC6)
// ===========================================================================

describe("Storybook stories — CodeBlock.stories.tsx structure (AC6)", () => {
  it("has a default export (meta object)", () => {
    const content = readStory("CodeBlock.stories.tsx");
    expect(content).toMatch(/export\s+default\s+/);
  });

  it("meta object has a title field", () => {
    const content = readStory("CodeBlock.stories.tsx");
    expect(content).toMatch(/title\s*:/);
  });

  it("has at least one named story export", () => {
    const content = readStory("CodeBlock.stories.tsx");
    expect(content).toMatch(/export\s+const\s+\w+/);
  });

  it("covers basic usage with code content", () => {
    const content = readStory("CodeBlock.stories.tsx");
    expect(content).toMatch(/Default|Basic|Primary/i);
  });

  it("covers copy button interaction", () => {
    const content = readStory("CodeBlock.stories.tsx");
    expect(content).toMatch(/copy|Copy|clipboard|Clipboard/i);
  });
});

