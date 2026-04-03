/**
 * RED-TEAM tests for RUN-355 / RUN-460: wire the shared provider modal to the
 * canvas topbar trigger.
 *
 * Source-reading pattern: verify structural properties by reading source files.
 *
 * Current state (all tests expected to FAIL):
 *   - CanvasPage does NOT import or render the shared ProviderModal
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

// ===========================================================================
// 1. CanvasPage imports and renders ProviderModal (AC1, AC2)
// ===========================================================================

describe("CanvasPage imports and renders ProviderModal (RUN-355 / RUN-460)", () => {
  it("imports ProviderModal from components/provider/ProviderModal", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).toMatch(
      /import.*ProviderModal.*from.*components\/provider\/ProviderModal|@\/components\/provider\/ProviderModal/,
    );
  });

  it("renders <ProviderModal in JSX", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).toMatch(/<ProviderModal\b/);
  });

  it("passes open prop to ProviderModal", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).toMatch(/<ProviderModal[\s\S]*?\bopen[=\s{]/);
  });

  it("passes onOpenChange prop to ProviderModal", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).toMatch(/<ProviderModal[\s\S]*?onOpenChange/);
  });

  it("passes onSaveSuccess callback to ProviderModal", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).toMatch(/<ProviderModal[\s\S]*?onSaveSuccess/);
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
// 3. Removed — ExploreBanner was deleted in RUN-559
// (explore banner is now rendered via PriorityBanner conditions in CanvasPage)
// ===========================================================================

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
    expect(topbarSource).toMatch(/<RunButton[\s\S]*?onAddApiKey/);
  });

  it("CanvasTopbar accepts onAddApiKey in its props", () => {
    const topbarSource = readSource("features/canvas/CanvasTopbar.tsx");
    expect(topbarSource).toMatch(/onAddApiKey/);
  });

  it("CanvasPage passes onAddApiKey to CanvasTopbar", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).toMatch(/<CanvasTopbar[\s\S]*?onAddApiKey/);
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
// 8b. RunButton swaps to "Run" when providers exist (AC3)
// ===========================================================================

describe("RunButton swaps to Run when providers exist (RUN-355 AC3)", () => {
  it("RunButton uses useProviders() to determine provider state", () => {
    const source = readSource(RUN_BUTTON_PATH);
    expect(source).toMatch(/useProviders/);
  });

  it("RunButton conditionally renders Add API Key vs Run based on hasProviders", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // Should have conditional logic based on providers being present
    const hasConditional =
      /hasProviders|items\.length/.test(source) &&
      /Add API Key/.test(source) &&
      /Run/.test(source);
    expect(
      hasConditional,
      "Expected RunButton to conditionally render Add API Key vs Run based on provider state",
    ).toBe(true);
  });

  it("ProviderModal.onSaveSuccess triggers query invalidation so RunButton re-renders", () => {
    // ProviderModal calls onSaveSuccess, CanvasPage's handler should invalidate
    // provider queries — causing useProviders() in RunButton to refetch
    const source = readSource(CANVAS_PAGE_PATH);
    const hasInvalidation =
      /invalidateQueries|queryClient/.test(source) ||
      // Or the modal itself handles invalidation and the callback just closes
      /onSaveSuccess/.test(source);
    expect(
      hasInvalidation,
      "Expected save success flow to trigger provider query invalidation",
    ).toBe(true);
  });
});

// ===========================================================================
// 9. Save & Run triggers execution (AC4)
// ===========================================================================

describe("Save & Run triggers workflow execution (RUN-355 AC4)", () => {
  it("ProviderModal receives canvas mode from CanvasPage", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    expect(source).toMatch(/<ProviderModal[\s\S]*?mode=["']canvas["']/);
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
// 10. Removed — ExploreBanner was deleted in RUN-559
// (explore banner auto-hide and dismiss now handled via PriorityBanner)
// ===========================================================================

// ===========================================================================
// 11. Focus returns to trigger element on modal close (AC5)
// ===========================================================================

describe("Focus returns to trigger element on modal close (RUN-355 AC5)", () => {
  it("CanvasPage creates a ref for the modal trigger element", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // Should have a useRef for the trigger element (button that opened the modal)
    // e.g. triggerRef, apiKeyTriggerRef, modalTriggerRef
    const hasRef =
      /triggerRef|apiKeyTriggerRef|modalTriggerRef/.test(source);
    expect(
      hasRef,
      "Expected CanvasPage to create a ref for the modal trigger element",
    ).toBe(true);
  });

  it("modal close handler restores focus to the trigger ref", () => {
    const source = readSource(CANVAS_PAGE_PATH);
    // On modal close, should call .focus() on the trigger ref
    const restoresFocus =
      /triggerRef.*\.current.*\.focus\(\)|modalTriggerRef.*\.current.*\.focus\(\)|apiKeyTriggerRef.*\.current.*\.focus\(\)|\.current\?*\.focus\(\)/.test(source);
    expect(
      restoresFocus,
      "Expected modal close handler to call focus() on the trigger ref",
    ).toBe(true);
  });
});

// ===========================================================================
// 12. No new Zustand stores for modal state
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
