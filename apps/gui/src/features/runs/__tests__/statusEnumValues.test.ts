/**
 * Run status query parameter coverage.
 *
 * Run list filters must send backend RunStatus enum values as separate query
 * parameters. Behavioral tests mock `fetch`, call `runsApi.listRuns()`, and
 * verify the actual URL query string sent to the backend.
 *
 * - Active tab sends running and pending as separate status params
 * - History tab sends completed and failed as separate status params
 * - No comma-separated or UI-only status aliases reach the API boundary
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
// ---------------------------------------------------------------------------

describe("Active tab status params", () => {
  it("should include 'running' in status query params", async () => {
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
// ---------------------------------------------------------------------------

describe("History tab status params", () => {
  it("should include 'completed' as a separate status query param", async () => {
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

describe("URLSearchParams produces correct multi-value status URLs", () => {
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
