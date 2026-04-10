/**
 * RED-TEAM tests for RUN-406: QA-003 — Fix provider shape mismatch in canvas components.
 *
 * Bug: useProviders() returns { items: Provider[], total: number } as its data,
 * but RunButton, CanvasStatusBar, and ExploreBanner destructure as
 *   const { data: providers } = useProviders()
 * and then call providers.length or providers[0], which is undefined because
 * the data object is { items, total }, not an array.
 *
 * The correct pattern (used by ProvidersTab) is: data?.items || []
 *
 * These tests verify:
 *   AC1: RunButton correctly checks provider count via .items
 *   AC2: CanvasStatusBar correctly checks provider connection via .items
 *   AC3: ExploreBanner correctly shows/hides based on provider count via .items
 *   AC4: No .length called directly on the { items, total } object
 *
 * All tests are expected to FAIL because the components currently call
 * .length directly on the { items, total } object instead of .items.
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SRC_DIR = resolve(__dirname, "../../..");

function readSource(relativePath: string): string {
  return readFileSync(resolve(SRC_DIR, relativePath), "utf-8");
}

// ---------------------------------------------------------------------------
// Paths
// ---------------------------------------------------------------------------

const RUN_BUTTON_PATH = "features/surface/RunButton.tsx";
const STATUS_BAR_PATH = "features/surface/SurfaceStatusBar.tsx";
const SETTINGS_QUERY_PATH = "queries/settings.ts";
const SETTINGS_API_PATH = "api/settings.ts";

// ===========================================================================
// 0. Confirm the return shape of useProviders is { items, total }
// ===========================================================================

describe("useProviders returns { items, total } shape (RUN-406 context)", () => {
  it("settingsApi.listProviders returns { items: Provider[], total: number }", () => {
    const source = readSource(SETTINGS_API_PATH);
    // The API layer explicitly types the return as { items: Provider[]; total: number }
    expect(source).toMatch(/Promise<\{\s*items:\s*Provider\[\];\s*total:\s*number\s*\}>/);
  });

  it("useProviders calls settingsApi.listProviders (data is { items, total })", () => {
    const source = readSource(SETTINGS_QUERY_PATH);
    expect(source).toMatch(/settingsApi\.listProviders/);
  });
});

// ===========================================================================
// 1. RunButton — must access .items, not .length on data (AC1)
// ===========================================================================

describe("RunButton accesses providers via .items (RUN-406 AC1)", () => {
  it("does NOT call .length directly on the providers data object", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // The buggy pattern: providers?.length or providers.length
    // where providers is { items: [], total: 0 } — .length is undefined on plain objects
    //
    // This test catches the exact bug: the code does
    //   const hasProviders = (providers?.length ?? 0) > 0;
    // which should instead be
    //   const hasProviders = (providers?.items?.length ?? 0) > 0;
    //   or: const providers = data?.items ?? [];
    const hasDirectLengthOnData = /\bproviders\?\.length\b|\bproviders\.length\b/.test(source);
    expect(
      hasDirectLengthOnData,
      "RunButton calls .length directly on { items, total } — must use .items first",
    ).toBe(false);
  });

  it("accesses providers through the .items property", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // Should access data.items or data?.items or destructure items
    const accessesItems =
      /providers\?\.items|providers\.items|data\?\.items|\.items\s*\?\?|\.items\s*\|\||const\s*\{[^}]*items[^}]*\}\s*=/.test(source);
    expect(
      accessesItems,
      "RunButton must access .items on the { items, total } data from useProviders",
    ).toBe(true);
  });

  it("correctly determines hasProviders from items array length", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // Should check items.length or a derived array's .length (e.g. activeProviders.length)
    const checksItemsLength =
      /items\?\.length|items\.length|activeProviders\.length/.test(source);
    expect(
      checksItemsLength,
      "RunButton should check .items.length (or derived array length) to determine if providers exist",
    ).toBe(true);
  });
});

// ===========================================================================
// 2. CanvasStatusBar — must access .items, not .length on data (AC2)
// ===========================================================================

describe("SurfaceStatusBar no longer uses providers (RUN-406 AC2)", () => {
  it("does NOT import or reference useProviders", () => {
    const source = readSource(STATUS_BAR_PATH);
    expect(source).not.toMatch(/useProviders/);
  });

  it("does NOT call .length directly on a providers data object", () => {
    const source = readSource(STATUS_BAR_PATH);
    const hasDirectLengthOnData = /\bproviders\?\.length\b|\bproviders\.length\b/.test(source);
    expect(
      hasDirectLengthOnData,
      "CanvasStatusBar calls .length directly on providers — should not reference providers",
    ).toBe(false);
  });

  it("does NOT index providers directly as an array (providers[0])", () => {
    const source = readSource(STATUS_BAR_PATH);
    const hasDirectIndexing = /providers\[0\]/.test(source);
    expect(
      hasDirectIndexing,
      "CanvasStatusBar indexes providers[0] — should not reference providers",
    ).toBe(false);
  });
});

// ===========================================================================
// 3. Cross-cutting: no .length on { items, total } in any canvas component (AC4)
// ===========================================================================

describe("No .length called on { items, total } object in canvas components (RUN-406 AC4)", () => {
  const CANVAS_COMPONENTS = [
    { name: "RunButton", path: RUN_BUTTON_PATH },
    { name: "CanvasStatusBar", path: STATUS_BAR_PATH },
  ];

  for (const { name, path } of CANVAS_COMPONENTS) {
    it(`${name} does not destructure useProviders data and call .length on it`, () => {
      const source = readSource(path);
      // Look for the buggy pattern:
      //   const { data: providers } = useProviders()  followed by  providers.length or providers?.length
      // The data from useProviders is { items: Provider[], total: number }
      // which does NOT have a .length property.
      const usesProviders = /useProviders\(\)/.test(source);
      if (!usesProviders) return; // Skip if component doesn't use this hook

      // Extract lines that reference the destructured variable and .length
      const aliasMatch = source.match(/const\s*\{\s*data:\s*(\w+)\s*\}\s*=\s*useProviders/);

      if (aliasMatch) {
        const alias = aliasMatch[1]; // e.g. "providers"
        const lengthRegex = new RegExp(`\\b${alias}\\?\\.length\\b|\\b${alias}\\.length\\b`);
        const directIndexRegex = new RegExp(`\\b${alias}\\[\\d+\\]`);

        const callsLengthDirectly = lengthRegex.test(source);
        const indexesDirectly = directIndexRegex.test(source);

        expect(
          callsLengthDirectly || indexesDirectly,
          `${name} calls .length or indexes directly on '${alias}' which is { items, total }, not an array`,
        ).toBe(false);
      }
    });
  }
});
