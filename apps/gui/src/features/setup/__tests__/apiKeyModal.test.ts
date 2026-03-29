/**
 * RED-TEAM tests for RUN-354: API key modal redesign — single-screen form.
 *
 * Source-reading pattern: verify structural properties by reading source files.
 *
 * Replaces the 3-step ProviderSetup wizard with a single-screen ApiKeyModal.
 *
 * AC1: Single screen: dropdown + key input + auto-test inline
 * AC2: No step navigation (no back/next buttons)
 * AC3: Auto-test fires 1s after key input stops
 * AC4: Success: green dot + "Connected · N models"
 * AC5: Error: red dot + error message
 * AC6: "Save & Run" enabled only after successful test
 * AC7: Base URL shown only for Custom provider
 * AC8: Modal reusable from canvas and settings
 * AC9: Matches component tree from spec
 *
 * Expected failures (current state):
 *   - ApiKeyModal.tsx does not exist
 *   - useApiKeyAutoTest.ts does not exist
 *   - ConnectionFeedback.tsx does not exist
 */

import { describe, it, expect } from "vitest";
import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SRC_DIR = resolve(__dirname, "../../..");

function readSource(relativePath: string): string {
  return readFileSync(resolve(SRC_DIR, relativePath), "utf-8");
}

function fileExists(relativePath: string): boolean {
  return existsSync(resolve(SRC_DIR, relativePath));
}

// ---------------------------------------------------------------------------
// File paths
// ---------------------------------------------------------------------------

const API_KEY_MODAL_PATH = "features/setup/ApiKeyModal.tsx";
const AUTO_TEST_HOOK_PATH = "features/setup/hooks/useApiKeyAutoTest.ts";
const CONNECTION_FEEDBACK_PATH = "features/setup/components/ConnectionFeedback.tsx";

// ===========================================================================
// 1. New files exist
// ===========================================================================

describe("New component files exist", () => {
  it("ApiKeyModal.tsx exists", () => {
    expect(
      fileExists(API_KEY_MODAL_PATH),
      "Expected features/setup/ApiKeyModal.tsx to exist",
    ).toBe(true);
  });

  it("useApiKeyAutoTest.ts hook exists", () => {
    expect(
      fileExists(AUTO_TEST_HOOK_PATH),
      "Expected features/setup/hooks/useApiKeyAutoTest.ts to exist",
    ).toBe(true);
  });

  it("ConnectionFeedback.tsx exists", () => {
    expect(
      fileExists(CONNECTION_FEEDBACK_PATH),
      "Expected features/setup/components/ConnectionFeedback.tsx to exist",
    ).toBe(true);
  });
});

// ===========================================================================
// 2. ApiKeyModal exports and Dialog wrapper
// ===========================================================================

describe("ApiKeyModal exports and Dialog wrapper", () => {
  it("exports ApiKeyModal component", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    expect(source).toMatch(/export\s+(function|const)\s+ApiKeyModal/);
  });

  it("imports Dialog from @runsight/ui/dialog", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    expect(source).toMatch(/import.*Dialog.*from.*@runsight\/ui\/dialog/);
  });

  it("imports DialogContent from @runsight/ui/dialog", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    expect(source).toMatch(/import.*DialogContent.*from.*@runsight\/ui\/dialog/);
  });

  it("imports DialogHeader from @runsight/ui/dialog", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    expect(source).toMatch(/import.*DialogHeader.*from.*@runsight\/ui\/dialog/);
  });

  it("imports DialogFooter from @runsight/ui/dialog", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    expect(source).toMatch(/import.*DialogFooter.*from.*@runsight\/ui\/dialog/);
  });

  it("constrains dialog width to max-w-[440px]", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    expect(source).toMatch(/max-w-\[440px\]/);
  });

  it("has dialog title 'Add API Key'", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    expect(source).toMatch(/Add API Key/);
  });
});

// ===========================================================================
// 3. ApiKeyModal props interface (AC8 — reusable from canvas and settings)
// ===========================================================================

describe("ApiKeyModal props interface", () => {
  it("has 'open' prop in interface", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    expect(source).toMatch(/open\s*:\s*boolean/);
  });

  it("has 'onOpenChange' prop in interface", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    expect(source).toMatch(/onOpenChange\s*:\s*\(.*\)\s*=>\s*void/);
  });

  it("has 'onSaveSuccess' optional callback prop", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    expect(source).toMatch(/onSaveSuccess\?\s*:/);
  });

  it("has 'saveAndRun' boolean prop for canvas vs settings context", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    expect(source).toMatch(/saveAndRun\?\s*:\s*boolean/);
  });

  it("passes open prop to Dialog component", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    expect(source).toMatch(/<Dialog[\s\S]*?open/);
  });

  it("passes onOpenChange prop to Dialog component", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    expect(source).toMatch(/<Dialog[\s\S]*?onOpenChange/);
  });
});

// ===========================================================================
// 4. Provider Select dropdown (AC1 — single screen with dropdown)
// ===========================================================================

describe("Provider Select dropdown", () => {
  it("imports Select from @runsight/ui/select", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    expect(source).toMatch(/import.*Select.*from.*@runsight\/ui\/select/);
  });

  it("imports ALL_PROVIDERS from ProviderSetup", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    expect(source).toMatch(/import.*ALL_PROVIDERS/);
  });

  it("renders SelectItem for each provider (10 options)", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    // Should map over ALL_PROVIDERS to create select items
    expect(source).toMatch(/ALL_PROVIDERS.*map|\.map.*SelectItem/);
  });

  it("defaults to OpenAI provider", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    // Should have openai as default value
    expect(source).toMatch(/["']openai["']/);
  });
});

// ===========================================================================
// 5. API key masked input with visibility toggle (AC1)
// ===========================================================================

describe("API key masked input with visibility toggle", () => {
  it("imports Input from @runsight/ui/input", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    expect(source).toMatch(/import.*Input.*from.*@runsight\/ui\/input/);
  });

  it("has password type input for API key", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    expect(source).toMatch(/type.*password|password.*type/);
  });

  it("uses mono font on key input", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    expect(source).toMatch(/font-mono/);
  });

  it("has eye toggle for visibility (Eye/EyeOff icons)", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    const hasEye = /Eye|EyeOff/.test(source);
    expect(hasEye, "Expected Eye/EyeOff icon imports for visibility toggle").toBe(true);
  });

  it("toggles between password and text type", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    // Should conditionally set type based on show state
    const hasToggle = /showApiKey|showKey|showPassword|isVisible/.test(source);
    expect(hasToggle, "Expected visibility toggle state variable").toBe(true);
  });
});

// ===========================================================================
// 6. Provider-specific helper link
// ===========================================================================

describe("Provider-specific helper link", () => {
  it("renders a helper link below the key input", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    // Should have an anchor or link component with provider-specific URL
    const hasLink = /<a\s|href=|HelperLink/.test(source);
    expect(hasLink, "Expected helper link element below key input").toBe(true);
  });

  it("link is provider-specific (changes based on selected provider)", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    // Should reference the selected provider to determine the URL
    const hasProviderUrl = /docsUrl|helperUrl|apiKeyUrl|provider.*url|url.*provider/i.test(source);
    expect(hasProviderUrl, "Expected provider-specific URL logic").toBe(true);
  });
});

// ===========================================================================
// 7. ConnectionFeedback component
// ===========================================================================

describe("ConnectionFeedback component", () => {
  it("exports ConnectionFeedback", () => {
    const source = readSource(CONNECTION_FEEDBACK_PATH);
    expect(source).toMatch(/export\s+(function|const)\s+ConnectionFeedback/);
  });

  it("handles 'testing' status with spinner", () => {
    const source = readSource(CONNECTION_FEEDBACK_PATH);
    // Should show spinner/loader for testing state
    const hasSpinner = /Loader2|animate-spin|spinner/i.test(source);
    expect(hasSpinner, "Expected spinner for testing status").toBe(true);
  });

  it("handles 'success' status with 'Connected' text (AC4)", () => {
    const source = readSource(CONNECTION_FEEDBACK_PATH);
    expect(source).toMatch(/Connected/);
  });

  it("shows model count in success state — 'Connected · N models' pattern (AC4)", () => {
    const source = readSource(CONNECTION_FEEDBACK_PATH);
    // Should display model count alongside "Connected"
    const hasModelCount = /models|model_count|modelCount/.test(source);
    expect(hasModelCount, "Expected model count display in success state").toBe(true);
  });

  it("uses green indicator for success (AC4)", () => {
    const source = readSource(CONNECTION_FEEDBACK_PATH);
    const hasGreen = /success|green|bg-green|text-green|success-9/.test(source);
    expect(hasGreen, "Expected green indicator for success state").toBe(true);
  });

  it("handles 'error' status with error display (AC5)", () => {
    const source = readSource(CONNECTION_FEEDBACK_PATH);
    const hasError = /error|danger|red|XCircle/.test(source);
    expect(hasError, "Expected error indicator for error state").toBe(true);
  });

  it("accepts status prop with TestStatus type", () => {
    const source = readSource(CONNECTION_FEEDBACK_PATH);
    expect(source).toMatch(/status/);
  });

  it("is used inside ApiKeyModal", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    expect(source).toMatch(/ConnectionFeedback/);
  });
});

// ===========================================================================
// 8. useApiKeyAutoTest hook
// ===========================================================================

describe("useApiKeyAutoTest hook", () => {
  it("exports useApiKeyAutoTest", () => {
    const source = readSource(AUTO_TEST_HOOK_PATH);
    expect(source).toMatch(/export\s+(function|const)\s+useApiKeyAutoTest/);
  });

  it("imports useCreateProvider from queries/settings", () => {
    const source = readSource(AUTO_TEST_HOOK_PATH);
    expect(source).toMatch(/import.*useCreateProvider.*from.*queries\/settings/);
  });

  it("imports useTestProviderConnection from queries/settings", () => {
    const source = readSource(AUTO_TEST_HOOK_PATH);
    expect(source).toMatch(/import.*useTestProviderConnection.*from.*queries\/settings/);
  });

  it("imports useDeleteProvider for cleanup on cancel", () => {
    const source = readSource(AUTO_TEST_HOOK_PATH);
    expect(source).toMatch(/import.*useDeleteProvider.*from.*queries\/settings/);
  });

  it("has debounce logic with ~1000ms delay (AC3)", () => {
    const source = readSource(AUTO_TEST_HOOK_PATH);
    // Should reference 1000ms debounce
    const hasDebounce = /1000|debounce/i.test(source);
    expect(hasDebounce, "Expected 1000ms debounce delay").toBe(true);
  });

  it("uses setTimeout for debounce", () => {
    const source = readSource(AUTO_TEST_HOOK_PATH);
    expect(source).toMatch(/setTimeout/);
  });

  it("returns test status (idle/testing/success/error)", () => {
    const source = readSource(AUTO_TEST_HOOK_PATH);
    // Should return status that can be idle, testing, success, or error
    const hasStatus = /status|testStatus|TestStatus/.test(source);
    expect(hasStatus, "Expected test status in hook return value").toBe(true);
  });

  it("has cleanup function to delete provider on cancel", () => {
    const source = readSource(AUTO_TEST_HOOK_PATH);
    // Should have a cleanup/cancel mechanism that calls deleteProvider
    const hasCleanup = /cleanup|cancel|deleteProvider|delete/.test(source);
    expect(hasCleanup, "Expected cleanup/cancel logic that deletes provider").toBe(true);
  });

  it("is used inside ApiKeyModal", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    expect(source).toMatch(/useApiKeyAutoTest/);
  });
});

// ===========================================================================
// 9. Base URL conditional — only for Custom provider (AC7)
// ===========================================================================

describe("Base URL shown only for Custom provider (AC7)", () => {
  it("has a base URL input", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    // Should have a Base URL or baseUrl field
    const hasBaseUrl = /base.*url|baseUrl|Base URL/i.test(source);
    expect(hasBaseUrl, "Expected base URL input in modal").toBe(true);
  });

  it("conditionally renders base URL based on provider selection", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    // Base URL should be shown only for custom (and possibly ollama) provider
    const hasConditional = /custom|isCustom|Custom/.test(source);
    expect(hasConditional, "Expected conditional render for custom provider").toBe(true);
  });
});

// ===========================================================================
// 10. Save & Run button (AC6 — enabled only after successful test)
// ===========================================================================

describe('"Save & Run" button enabled only after successful test (AC6)', () => {
  it("imports Button from @runsight/ui/button", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    expect(source).toMatch(/import.*Button.*from.*@runsight\/ui\/button/);
  });

  it("has a 'Save' button (primary action)", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    expect(source).toMatch(/Save/);
  });

  it("Save button is disabled until test succeeds", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    // disabled prop should be tied to test status !== success
    const hasDisabled = /disabled.*success|disabled.*testStatus|disabled.*status/i.test(source);
    expect(
      hasDisabled,
      "Expected Save button disabled until test status is success",
    ).toBe(true);
  });

  it("has a Cancel button (secondary)", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    expect(source).toMatch(/Cancel/);
  });

  it("Cancel button uses secondary variant", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    // Cancel button should use variant="secondary" near the Cancel text
    const buttonBeforeCancel = source.match(/Button[\s\S]{0,200}Cancel/);
    const hasSecondary = buttonBeforeCancel
      ? /secondary/.test(buttonBeforeCancel[0])
      : false;
    expect(hasSecondary, "Expected Cancel button with secondary variant").toBe(true);
  });

  it("calls onSaveSuccess callback on save", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    expect(source).toMatch(/onSaveSuccess/);
  });

  it("closes modal after successful save", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    // Should call onOpenChange(false) after save
    expect(source).toMatch(/onOpenChange\s*\(\s*false\s*\)/);
  });
});

// ===========================================================================
// 11. No step navigation — no wizard pattern (AC2)
// ===========================================================================

describe("No step navigation — single screen (AC2)", () => {
  it("does not contain 'Step 1' text", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    expect(source).not.toMatch(/Step 1/);
  });

  it("does not contain 'Step 2' text", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    expect(source).not.toMatch(/Step 2/);
  });

  it("does not contain 'Step 3' text", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    expect(source).not.toMatch(/Step 3/);
  });

  it("does not have a 'Back' button", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    // Should NOT have back/previous navigation
    expect(source).not.toMatch(/>Back</);
    expect(source).not.toMatch(/>\s*Back\s*</);
  });

  it("does not have a 'Next' button", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    expect(source).not.toMatch(/>Next</);
    expect(source).not.toMatch(/>\s*Next\s*</);
  });

  it("does not import ProviderSetup component (replaces it)", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    expect(source).not.toMatch(/import.*ProviderSetup/);
  });

  it("does not reference step1Done or step2Done", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    expect(source).not.toMatch(/step1Done|step2Done/);
  });
});

// ===========================================================================
// 12. Cleanup on cancel — delete provider if created during auto-test
// ===========================================================================

describe("Cleanup on cancel — delete provider if created", () => {
  it("ApiKeyModal handles cancel with cleanup", () => {
    const source = readSource(API_KEY_MODAL_PATH);
    // Should have cancel handler that triggers cleanup
    const hasCancel = /cancel|handleCancel|handleClose|onCancel/.test(source);
    expect(hasCancel, "Expected cancel handler in ApiKeyModal").toBe(true);
  });

  it("hook exposes cleanup function", () => {
    const source = readSource(AUTO_TEST_HOOK_PATH);
    // Should return or expose a cleanup function
    const hasCleanup = /cleanup|cancel|reset/.test(source);
    expect(hasCleanup, "Expected cleanup function in hook").toBe(true);
  });

  it("cleanup calls deleteProvider mutation", () => {
    const source = readSource(AUTO_TEST_HOOK_PATH);
    // deleteProvider should be called during cleanup
    const hasDelete = /deleteProvider.*mutate|delete.*Provider/.test(source);
    expect(hasDelete, "Expected deleteProvider call in cleanup").toBe(true);
  });
});
