/**
 * RED-TEAM tests for RUN-405: Fix frontend status enum mismatch in RunList.
 *
 * Bug: RunList.tsx line 542 sends `status: "active"` and `status: "completed,failed"`
 * as single strings. Backend expects `List[str]` with actual RunStatus enum values
 * (`running`, `pending`, `completed`, `failed`). `"active"` is not a valid enum value.
 *
 * These tests verify:
 * 1. The "Active" tab sends status params `running` and `pending` (NOT `"active"`)
 * 2. The "History" tab sends status params `completed` and `failed` (NOT `"completed,failed"`)
 * 3. The string `"active"` is never sent as a status value
 * 4. Status values are sent as separate entries (array/multi-param), not comma-separated
 *
 * Approach: Source-level analysis (read RunList.tsx, check the useRuns call patterns)
 * matching the project's established Vitest test convention.
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "fs";
import { resolve } from "path";

// Read RunList source once for behavioral source-level assertions.
const RUN_LIST_SOURCE = readFileSync(
  resolve(__dirname, "../RunList.tsx"),
  "utf-8",
);

// ---------------------------------------------------------------------------
// Valid RunStatus enum values (from backend: RunStatus in domain/entities/run.py)
// ---------------------------------------------------------------------------

const VALID_RUN_STATUS_VALUES = [
  "pending",
  "running",
  "completed",
  "failed",
  "cancelled",
] as const;

// ---------------------------------------------------------------------------
// 1. Active tab must use actual enum values, not "active"
// ---------------------------------------------------------------------------

describe("Active tab sends correct status enum values (RUN-405)", () => {
  it("does NOT send status: \"active\" anywhere in RunList", () => {
    // The string "active" is not a valid RunStatus enum value.
    // The active tab should send ["running", "pending"] instead.
    //
    // Match patterns like: status: "active", { status: "active" }, status: 'active'
    const sendsActiveAsStatus =
      /\bstatus\s*:\s*["']active["']/.test(RUN_LIST_SOURCE);

    expect(sendsActiveAsStatus).toBe(false);
  });

  it("active tab query includes status \"running\"", () => {
    // When the active tab is selected, the useRuns call must include "running"
    // as one of the status values. Look for "running" being used as a status param.
    //
    // Acceptable patterns:
    //   - status: ["running", "pending"]  (array literal)
    //   - params.append("status", "running")  (URLSearchParams)
    //   - A variable/constant that resolves to include "running"
    const includesRunning =
      // Array literal with "running"
      /\bstatus\b[^;]*\[.*["']running["'].*\]/.test(RUN_LIST_SOURCE) ||
      // URLSearchParams append
      /append\s*\(\s*["']status["']\s*,\s*["']running["']\s*\)/.test(RUN_LIST_SOURCE) ||
      // Status param construction referencing "running" near "active" tab logic
      /tab\s*===?\s*["']active["'][^}]*["']running["']/.test(RUN_LIST_SOURCE) ||
      // Ternary or conditional with array containing "running"
      /active["'][^?]*\?\s*.*["']running["']/.test(RUN_LIST_SOURCE);

    expect(includesRunning).toBe(true);
  });

  it("active tab query includes status \"pending\"", () => {
    // When the active tab is selected, "pending" must also be included
    // alongside "running".
    const includesPending =
      /\bstatus\b[^;]*\[.*["']pending["'].*\]/.test(RUN_LIST_SOURCE) ||
      /append\s*\(\s*["']status["']\s*,\s*["']pending["']\s*\)/.test(RUN_LIST_SOURCE) ||
      /tab\s*===?\s*["']active["'][^}]*["']pending["']/.test(RUN_LIST_SOURCE) ||
      /active["'][^?]*\?\s*.*["']pending["']/.test(RUN_LIST_SOURCE);

    expect(includesPending).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// 2. History tab must send separate enum values, not "completed,failed"
// ---------------------------------------------------------------------------

describe("History tab sends correct status enum values (RUN-405)", () => {
  it("does NOT send status: \"completed,failed\" as a comma-separated string", () => {
    // "completed,failed" is a single string containing a comma — the backend
    // will try to match it as one enum value and fail.
    // Must be sent as separate values: ["completed", "failed"] or via
    // URLSearchParams with multiple appends.
    const sendsCommaSeparated =
      /\bstatus\s*:\s*["']completed,failed["']/.test(RUN_LIST_SOURCE);

    expect(sendsCommaSeparated).toBe(false);
  });

  it("history tab query includes status \"completed\" as a separate value", () => {
    // "completed" must appear as its own string value, not part of "completed,failed"
    const includesCompleted =
      // Array literal with "completed" (not followed by comma and "failed" in same string)
      /\bstatus\b[^;]*\[.*["']completed["'].*\]/.test(RUN_LIST_SOURCE) ||
      // URLSearchParams append
      /append\s*\(\s*["']status["']\s*,\s*["']completed["']\s*\)/.test(RUN_LIST_SOURCE);

    expect(includesCompleted).toBe(true);
  });

  it("history tab query includes status \"failed\" as a separate value", () => {
    // "failed" must appear as its own string value, not part of "completed,failed"
    const includesFailed =
      // Array literal with "failed"
      /\bstatus\b[^;]*\[.*["']failed["'].*\]/.test(RUN_LIST_SOURCE) ||
      // URLSearchParams append
      /append\s*\(\s*["']status["']\s*,\s*["']failed["']\s*\)/.test(RUN_LIST_SOURCE);

    expect(includesFailed).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// 3. No invalid status strings anywhere in the useRuns calls
// ---------------------------------------------------------------------------

describe("No invalid status strings in useRuns calls (RUN-405)", () => {
  it("\"active\" is not used as a status value in any useRuns call", () => {
    // Extract all useRuns calls from the source
    const useRunsCalls = RUN_LIST_SOURCE.match(/useRuns\s*\([^)]*\)/gs) ?? [];

    // None of the useRuns calls should contain the string "active" as a status
    for (const call of useRunsCalls) {
      expect(call).not.toMatch(/["']active["']/);
    }
  });

  it("no comma-separated status strings are used in any useRuns call", () => {
    // Extract all useRuns calls and check none contain comma-separated status values
    const useRunsCalls = RUN_LIST_SOURCE.match(/useRuns\s*\([^)]*\)/gs) ?? [];

    for (const call of useRunsCalls) {
      // Should not have patterns like status: "x,y" (comma inside quotes)
      expect(call).not.toMatch(/status\s*:\s*["'][^"']*,[^"']*["']/);
    }
  });

  it("all status values used in useRuns calls are valid RunStatus enum members", () => {
    // Find all quoted strings that appear as status values in useRuns context
    // Valid values: pending, running, completed, failed, cancelled
    const statusSection = RUN_LIST_SOURCE.match(
      /useRuns\s*\(\s*([\s\S]*?)\s*,\s*\{/g,
    );

    if (statusSection) {
      for (const section of statusSection) {
        // Extract all quoted strings from the status parameter area
        const quotedStrings = section.match(/["']([^"']+)["']/g) ?? [];
        for (const qs of quotedStrings) {
          const value = qs.replace(/["']/g, "");
          // Skip non-status strings (like "status" key name itself)
          if (value === "status") continue;
          // Every status value string must be a valid enum member
          expect(VALID_RUN_STATUS_VALUES).toContain(value);
        }
      }
    }
  });
});

// ---------------------------------------------------------------------------
// 4. Status values are sent as proper multi-value params (array or URLSearchParams)
// ---------------------------------------------------------------------------

describe("Status params are properly structured for backend List[str] (RUN-405)", () => {
  it("the useRuns call for the active tab uses an array or URLSearchParams, not a plain object with a single string", () => {
    // The bug: tab === "active" ? { status: "active" } : ...
    // The fix should use an array or URLSearchParams to send multiple status values.
    //
    // Acceptable:
    //   - useRuns with URLSearchParams that has multiple status appends
    //   - useRuns with an object containing status as an array
    //   - A helper that builds proper multi-value params
    //
    // Unacceptable:
    //   - { status: "active" }  (single string, wrong value)
    //   - { status: "running" } (single string, only one value)

    // The active tab condition in the source
    const activeTabMatch = RUN_LIST_SOURCE.match(
      /tab\s*===?\s*["']active["']\s*\?\s*([^:]+)\s*:/s,
    );

    // If the ternary pattern exists, check what the active branch produces
    if (activeTabMatch) {
      const activeBranch = activeTabMatch[1].trim();
      // Must NOT be a simple { status: "..." } with a single string value
      expect(activeBranch).not.toMatch(/^\{\s*status\s*:\s*["'][^"']+["']\s*\}$/);
    }

    // Additionally, confirm the overall pattern doesn't use single-string status
    // for the active tab. The useRuns call near 'active' should reference both
    // "running" and "pending".
    const useRunsArea = RUN_LIST_SOURCE.match(
      /useRuns\s*\(\s*[\s\S]{0,300}?refetchInterval/,
    );
    if (useRunsArea) {
      const area = useRunsArea[0];
      // Must contain both "running" and "pending"
      expect(area).toMatch(/["']running["']/);
      expect(area).toMatch(/["']pending["']/);
    }
  });

  it("the useRuns call for the history tab uses an array or URLSearchParams, not a comma-separated string", () => {
    // The bug: { status: "completed,failed" }
    // The fix should send "completed" and "failed" as separate values.

    // Extract the full useRuns call (may span multiple lines)
    const useRunsCall = RUN_LIST_SOURCE.match(/useRuns\s*\([\s\S]*?\)\s*;/);
    expect(useRunsCall).not.toBeNull();

    const callText = useRunsCall![0];

    // Find all quoted strings that look like status values containing commas
    // "completed,failed" is a comma inside a quoted string — that's the bug
    const commaInStatusString = /status\s*:\s*["'][^"']*,[^"']*["']/.test(callText);
    expect(commaInStatusString).toBe(false);

    // Additionally, the history-tab branch must not use a single string for
    // multiple status values. Look for the else-branch of the ternary:
    // the part after `:` and before the second argument to useRuns.
    // Extract the ternary else-branch more carefully.
    const elseBranch = callText.match(
      /\}\s*:\s*(\{[^}]+\})/,
    );
    if (elseBranch) {
      // The else branch should NOT have a single comma-separated string
      expect(elseBranch[1]).not.toMatch(/["']completed,failed["']/);
    }
  });
});
