/**
 * RED-TEAM tests for RUN-405: Fix frontend status enum mismatch in RunList.
 *
 * Bug: RunList.tsx line 542 sends `status: "active"` and `status: "completed,failed"`
 * as single strings to useRuns(). Backend expects `List[str]` with actual RunStatus
 * enum values (`running`, `pending`, `completed`, `failed`). `"active"` is not a valid
 * enum value; `"completed,failed"` is a single string containing a comma.
 *
 * Approach: Behavioral testing at the API boundary. We mock `fetch`, call
 * `runsApi.listRuns()` with the params that RunList currently passes, and verify
 * the actual URL query string sent to the backend. No source-code regex analysis.
 *
 * Test structure:
 *   - Group 1 (Active tab): asserts correct behavior → FAILS with current buggy params
 *   - Group 2 (History tab): asserts correct behavior → FAILS with current buggy params
 *   - Group 3 (Contract): validates that URLSearchParams fix path produces correct URLs → PASSES
 *
 * Green Team: fix RunList to pass URLSearchParams with separate status values to
 * useRuns(), then update the params in Groups 1 & 2 to match the new calling convention.
 * All tests should then pass.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// ---------------------------------------------------------------------------
// Valid RunStatus enum values (from backend: RunStatus in domain/entities/run.py)
// ---------------------------------------------------------------------------

const VALID_RUN_STATUS_VALUES = new Set([
  "pending",
  "running",
  "completed",
  "failed",
  "cancelled",
]);

// ---------------------------------------------------------------------------
// Test infrastructure: capture URLs sent to fetch by runsApi.listRuns
// ---------------------------------------------------------------------------

let capturedUrl: string | undefined;
const originalFetch = global.fetch;

function installFetchMock() {
  capturedUrl = undefined;
  global.fetch = vi.fn(async (input: string | URL | Request) => {
    capturedUrl = typeof input === "string" ? input : input.toString();
    return new Response(JSON.stringify({ items: [], total: 0 }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }) as unknown as typeof fetch;
}

async function callListRunsAndGetUrl(
  params: Record<string, string> | URLSearchParams | undefined,
): Promise<string> {
  const { runsApi } = await import("../../../api/runs");
  try {
    await runsApi.listRuns(params);
  } catch {
    // Zod parse may throw on mock response — we only need the captured URL
  }
  expect(capturedUrl).toBeDefined();
  return capturedUrl!;
}

function getQueryParamValues(url: string, paramName: string): string[] {
  const qsStart = url.indexOf("?");
  if (qsStart === -1) return [];
  return new URLSearchParams(url.slice(qsStart)).getAll(paramName);
}

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  installFetchMock();
});

afterEach(() => {
  global.fetch = originalFetch;
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// 1. Active tab: must produce URL with status=running AND status=pending
//
//    RunList currently passes { status: "active" } which yields ?status=active.
//    After fix it should yield ?status=running&status=pending.
// ---------------------------------------------------------------------------

describe("Active tab status params (RUN-405)", () => {
  it("should include 'running' in status query params", async () => {
    // Current buggy params from RunList line 542
    const url = await callListRunsAndGetUrl({ status: "active" });
    const values = getQueryParamValues(url, "status");

    expect(values).toContain("running");
  });

  it("should include 'pending' in status query params", async () => {
    const url = await callListRunsAndGetUrl({ status: "active" });
    const values = getQueryParamValues(url, "status");

    expect(values).toContain("pending");
  });

  it("should not include 'active' as a status value", async () => {
    const url = await callListRunsAndGetUrl({ status: "active" });
    const values = getQueryParamValues(url, "status");

    expect(values).not.toContain("active");
  });
});

// ---------------------------------------------------------------------------
// 2. History tab: must produce URL with status=completed AND status=failed
//
//    RunList currently passes { status: "completed,failed" } which yields
//    ?status=completed%2Cfailed. After fix: ?status=completed&status=failed.
// ---------------------------------------------------------------------------

describe("History tab status params (RUN-405)", () => {
  it("should include 'completed' as a separate status query param", async () => {
    // Current buggy params from RunList line 542
    const url = await callListRunsAndGetUrl({ status: "completed,failed" });
    const values = getQueryParamValues(url, "status");

    expect(values).toContain("completed");
  });

  it("should include 'failed' as a separate status query param", async () => {
    const url = await callListRunsAndGetUrl({ status: "completed,failed" });
    const values = getQueryParamValues(url, "status");

    expect(values).toContain("failed");
  });

  it("should not send any comma-separated status values", async () => {
    const url = await callListRunsAndGetUrl({ status: "completed,failed" });
    const values = getQueryParamValues(url, "status");

    for (const v of values) {
      expect(v).not.toContain(",");
    }
  });
});

// ---------------------------------------------------------------------------
// 3. Contract: URLSearchParams with separate status values produces correct URLs
//
//    Validates the fix path — when RunList switches to URLSearchParams,
//    the API layer correctly sends multiple status params.
// ---------------------------------------------------------------------------

describe("URLSearchParams produces correct multi-value status URLs (RUN-405)", () => {
  it("running + pending sent as separate status params", async () => {
    const params = new URLSearchParams();
    params.append("status", "running");
    params.append("status", "pending");

    const url = await callListRunsAndGetUrl(params);
    const values = getQueryParamValues(url, "status");

    expect(values).toHaveLength(2);
    expect(values).toContain("running");
    expect(values).toContain("pending");
    for (const v of values) {
      expect(VALID_RUN_STATUS_VALUES.has(v)).toBe(true);
    }
  });

  it("completed + failed sent as separate status params", async () => {
    const params = new URLSearchParams();
    params.append("status", "completed");
    params.append("status", "failed");

    const url = await callListRunsAndGetUrl(params);
    const values = getQueryParamValues(url, "status");

    expect(values).toHaveLength(2);
    expect(values).toContain("completed");
    expect(values).toContain("failed");
    for (const v of values) {
      expect(VALID_RUN_STATUS_VALUES.has(v)).toBe(true);
    }
  });
});
