/**
 * RED-TEAM tests for RUN-355: Wire API key modal to canvas topbar trigger.
 *
 * Source-reading pattern: verify structural properties by reading source files.
 *
 * Current state (all tests expected to FAIL):
 *   - CanvasPage does NOT import or render ApiKeyModal
 *   - CanvasPage has no apiKeyModalOpen state
 *   - CanvasPage does NOT pass onAddApiKey to ExploreBanner
 *   - RunButton navigates to /settings instead of calling an onAddApiKey callback
 *   - No save-success handler wiring between modal and canvas
 *
 * AC:
 *   AC1: "Add API Key" button in topbar opens modal
 *   AC2: Banner link opens same modal
 *   AC3: After save: button swaps to "Run", banner dismissed
 *   AC4: "Save & Run" saves key AND triggers workflow execution
 *   AC5: Focus returns to trigger element on modal close
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
// File paths
// ---------------------------------------------------------------------------

const CANVAS_PAGE_PATH = "features/canvas/CanvasPage.tsx";
const RUN_BUTTON_PATH = "features/canvas/RunButton.tsx";
const EXPLORE_BANNER_PATH = "features/canvas/ExploreBanner.tsx";

// ===========================================================================
// 1. CanvasPage imports and renders ApiKeyModal (AC1, AC2)
// ===========================================================================

describe("CanvasPage imports and renders ApiKeyModal (RUN-355)", () => {
  it("imports ApiKeyModal from features/setup/ApiKeyModal", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).toMatch(
      /import.*ApiKeyModal.*from.*features\/setup\/ApiKeyModal|@\/features\/setup\/ApiKeyModal/,
    );
  });

  it("renders <ApiKeyModal in JSX", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).toMatch(/<ApiKeyModal\b/);
  });

  it("passes open prop to ApiKeyModal", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).toMatch(/<ApiKeyModal[^>]*\bopen[=\s{]/);
  });

  it("passes onOpenChange prop to ApiKeyModal", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).toMatch(/<ApiKeyModal[^>]*onOpenChange/);
  });

  it("passes onSaveSuccess callback to ApiKeyModal", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).toMatch(/<ApiKeyModal[^>]*onSaveSuccess/);
  });
});

// ===========================================================================
// 2. CanvasPage has modal state (local useState, not Zustand)
// ===========================================================================

describe("CanvasPage has apiKeyModalOpen state (RUN-355)", () => {
  it("declares apiKeyModalOpen state via useState", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // Should have useState for modal open state — e.g. apiKeyModalOpen, isApiKeyModalOpen
    expect(source).toMatch(
      /useState.*apiKeyModal|apiKeyModal.*useState|isApiKeyModalOpen|setApiKeyModalOpen/i,
    );
  });

  it("has a setter function for the modal state", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // The setter should be named something like setApiKeyModalOpen
    expect(source).toMatch(/setApiKeyModalOpen|setIsApiKeyModalOpen|setModalOpen/);
  });
});

// ===========================================================================
// 3. CanvasPage passes onAddApiKey to ExploreBanner (AC2)
// ===========================================================================

describe("CanvasPage passes onAddApiKey to ExploreBanner (RUN-355 AC2)", () => {
  it("passes onAddApiKey prop to ExploreBanner", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).toMatch(/<ExploreBanner[^>]*onAddApiKey/);
  });

  it("onAddApiKey callback opens the modal", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // The callback passed to ExploreBanner should set modal state to true
    // e.g. onAddApiKey={() => setApiKeyModalOpen(true)}
    const hasModalOpener =
      /onAddApiKey=\{.*set.*Modal.*true|onAddApiKey=\{.*open.*Modal/i.test(source);
    expect(
      hasModalOpener,
      "Expected onAddApiKey to set modal open state to true",
    ).toBe(true);
  });
});

// ===========================================================================
// 4. RunButton accepts onAddApiKey prop (AC1)
// ===========================================================================

describe("RunButton accepts onAddApiKey prop (RUN-355 AC1)", () => {
  it("RunButton interface includes onAddApiKey prop", () => {
    const source = readSource(RUN_BUTTON_PATH);
    expect(source).toMatch(/onAddApiKey/);
  });

  it("RunButton destructures onAddApiKey from props", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // Should appear in the destructured props or function signature
    const hasDestructured =
      /\{\s*[^}]*onAddApiKey[^}]*\}/.test(source);
    expect(
      hasDestructured,
      "Expected onAddApiKey in destructured props",
    ).toBe(true);
  });
});

// ===========================================================================
// 5. RunButton no longer navigates to /settings (AC1)
// ===========================================================================

describe("RunButton no longer navigates to /settings (RUN-355)", () => {
  it("does NOT use window.location.href = '/settings'", () => {
    const source = readSource(RUN_BUTTON_PATH);
    expect(source).not.toMatch(/window\.location\.href\s*=\s*["']\/settings["']/);
  });

  it("does NOT use navigate('/settings')", () => {
    const source = readSource(RUN_BUTTON_PATH);
    expect(source).not.toMatch(/navigate\(["']\/settings["']\)/);
  });
});

// ===========================================================================
// 6. RunButton calls onAddApiKey when no providers (AC1)
// ===========================================================================

describe("RunButton calls onAddApiKey when no providers (RUN-355 AC1)", () => {
  it("Add API Key button onClick calls onAddApiKey", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // The onClick for the "Add API Key" button should invoke the onAddApiKey callback
    // instead of navigating to /settings
    const hasCallback =
      /onClick.*onAddApiKey|onAddApiKey\(\)/.test(source);
    expect(
      hasCallback,
      "Expected Add API Key button onClick to call onAddApiKey callback",
    ).toBe(true);
  });
});

// ===========================================================================
// 7. CanvasPage passes onAddApiKey to RunButton via CanvasTopbar (AC1)
// ===========================================================================

describe("CanvasPage wires onAddApiKey through to RunButton (RUN-355 AC1)", () => {
  it("CanvasTopbar passes onAddApiKey to RunButton", () => {
    const topbarSource = readSource("features/canvas/CanvasTopbar.tsx");
    expect(topbarSource).toMatch(/<RunButton[^>]*onAddApiKey/);
  });

  it("CanvasTopbar accepts onAddApiKey in its props", () => {
    const topbarSource = readSource("features/canvas/CanvasTopbar.tsx");
    expect(topbarSource).toMatch(/onAddApiKey/);
  });

  it("CanvasPage passes onAddApiKey to CanvasTopbar", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).toMatch(/<CanvasTopbar[^>]*onAddApiKey/);
  });
});

// ===========================================================================
// 8. CanvasPage handles save success — query invalidation (AC3)
// ===========================================================================

describe("CanvasPage handles save success (RUN-355 AC3)", () => {
  it("has a save success handler that closes the modal", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // On save success, should set modal open to false
    const closesModal =
      /onSaveSuccess|handleSaveSuccess|handleApiKeySaved/.test(source) &&
      /setApiKeyModalOpen\(false\)|setIsApiKeyModalOpen\(false\)|Modal.*false/.test(source);
    expect(
      closesModal,
      "Expected save success handler that closes the modal",
    ).toBe(true);
  });

  it("invalidates provider queries on save success", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // Should use queryClient.invalidateQueries or the onSaveSuccess from ApiKeyModal
    // already triggers invalidation — but the canvas page should handle the callback
    const hasInvalidation =
      /invalidateQueries|onSaveSuccess|queryClient/.test(source);
    expect(
      hasInvalidation,
      "Expected provider query invalidation on save success",
    ).toBe(true);
  });
});

// ===========================================================================
// 9. Save & Run triggers execution (AC4)
// ===========================================================================

describe("Save & Run triggers workflow execution (RUN-355 AC4)", () => {
  it("ApiKeyModal receives saveAndRun prop from CanvasPage", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).toMatch(/<ApiKeyModal[^>]*saveAndRun/);
  });

  it("save success handler triggers run when saveAndRun is true", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // After save+run, should call handleRun or createRun or trigger execution
    const triggersRun =
      /handleRun|createRun|triggerRun|startRun/.test(source);
    expect(
      triggersRun,
      "Expected save success handler to trigger workflow execution",
    ).toBe(true);
  });
});

// ===========================================================================
// 10. Explore banner dismissed on save (AC3)
// ===========================================================================

describe("Explore banner dismissed on save (RUN-355 AC3)", () => {
  it("CanvasPage dismisses explore banner after successful save", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // Should write to localStorage to persist banner dismissal
    const dismissesBanner =
      /localStorage.*explore.*banner|exploreBannerDismissed|explore-banner-dismissed/i.test(source);
    expect(
      dismissesBanner,
      "Expected localStorage write to dismiss explore banner on save",
    ).toBe(true);
  });

  it("ExploreBanner reads the same storage key for dismissal state", () => {
    const bannerSource = readSource(EXPLORE_BANNER_PATH);
    const canvasSource = readSource(CANVAS_PAGE_PATH);
    // Both should reference the same storage key
    const bannerKeyMatch = bannerSource.match(/["']([^"']*explore[^"']*dismiss[^"']*)["']/i)
      || bannerSource.match(/["']([^"']*explore[^"']*banner[^"']*)["']/i);
    expect(
      bannerKeyMatch,
      "Expected ExploreBanner to have a storage key for dismiss state",
    ).toBeTruthy();
    // Canvas page should reference the same key or the banner's STORAGE_KEY
    const storageKey = bannerKeyMatch?.[1];
    if (storageKey) {
      expect(canvasSource).toContain(storageKey);
    }
  });
});

// ===========================================================================
// 11. No new Zustand stores for modal state
// ===========================================================================

describe("No new Zustand stores for modal state (RUN-355)", () => {
  it("CanvasPage does NOT add modal state to useCanvasStore", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // Modal state should be local useState, not in the Zustand store
    expect(source).not.toMatch(
      /useCanvasStore.*apiKeyModal|useCanvasStore.*modalOpen/,
    );
  });

  it("canvas store has no apiKeyModal field", () => {
    const storeSource = readSource("store/canvas.ts");
    expect(storeSource).not.toMatch(/apiKeyModal/);
  });
});
