// @vitest-environment jsdom

/**
 * RED-TEAM tests for RUN-564: Fork Recovery — fork button + YAML-based fork flow.
 *
 * These tests cover all 8 AC items:
 *   AC1: Fork button visible in Run Detail header
 *   AC2: Click triggers git file read -> workflow creation -> navigation
 *   AC3: Auto-name follows `drft-{slug}-{uuid}` convention
 *   AC4: New workflow has `enabled: false`
 *   AC5: Fork button disabled during active execution with tooltip
 *   AC6: Fork button disabled when snapshot unavailable with tooltip
 *   AC7: Error shows toast, button re-enables
 *   AC8: No fork info banner (decision: removed)
 *
 * Test layers:
 *   1. Utility module contract — forkUtils.ts exports slugify, shortUuid, generateForkName
 *   2. Utility function behavior — slugify/shortUuid/generateForkName via require()
 *   3. API layer — gitApi.getGitFile
 *   4. Fork flow hook — useForkWorkflow
 *   5. Component integration — RunDetailHeader fork button
 *
 * All tests should FAIL because no fork implementation exists yet.
 */

import React from "react";
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider, useLocation } from "react-router";
import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

import { RunDetailHeader } from "../RunDetailHeader";

afterEach(() => {
  cleanup();
});

// ---------------------------------------------------------------------------
// Helpers — source analysis
// ---------------------------------------------------------------------------

const SRC_DIR = resolve(__dirname, "../../..");

function readSource(relativePath: string): string {
  const fullPath = resolve(SRC_DIR, relativePath);
  if (!existsSync(fullPath)) return "";
  return readFileSync(fullPath, "utf-8");
}

function fileExists(relativePath: string): boolean {
  return existsSync(resolve(SRC_DIR, relativePath));
}

// ---------------------------------------------------------------------------
// Helpers — component rendering
// ---------------------------------------------------------------------------

type RunStatus = "completed" | "failed" | "running" | "pending" | "error" | "success";

function LocationEcho() {
  const location = useLocation();
  return React.createElement("div", null, `location:${location.pathname}`);
}

function buildRun({
  status = "completed" as RunStatus,
  workflowId = "wf_research",
  workflowName = "Research & Review",
  commitSha = "abc123def456" as string | null,
} = {}) {
  return {
    id: "run_abcdef123456",
    workflow_id: workflowId,
    workflow_name: workflowName,
    status,
    total_cost_usd: 0.042,
    total_tokens: 1234,
    duration_seconds: 45,
    started_at: 1700000000,
    completed_at: 1700000045,
    created_at: 1700000000,
    commit_sha: commitSha,
  };
}

function renderHeader(options?: {
  status?: RunStatus;
  workflowId?: string;
  workflowName?: string;
  commitSha?: string | null;
}) {
  const run = buildRun(options);
  const router = createMemoryRouter(
    [
      {
        path: "/runs/:id",
        element: React.createElement(RunDetailHeader, { run }),
      },
      {
        path: "/workflows/:id/edit",
        element: React.createElement(LocationEcho),
      },
      {
        path: "/runs",
        element: React.createElement(LocationEcho),
      },
    ],
    { initialEntries: [`/runs/${run.id}`] },
  );

  const user = userEvent.setup();
  render(React.createElement(RouterProvider, { router }));

  return { router, user, run };
}

// ===========================================================================
// 1. Utility module contract — forkUtils.ts (AC3)
// ===========================================================================

describe("forkUtils.ts module contract (RUN-564 / AC3)", () => {
  it("forkUtils.ts exists in features/runs/", () => {
    expect(fileExists("features/runs/forkUtils.ts")).toBe(true);
  });

  it("forkUtils.ts is a pure module — no React imports", () => {
    const src = readSource("features/runs/forkUtils.ts");
    expect(src.length).toBeGreaterThan(0);
    expect(src).not.toMatch(/from\s+["']react["']/);
  });

  it("exports slugify", () => {
    const src = readSource("features/runs/forkUtils.ts");
    expect(src).toMatch(/export\s+(function|const)\s+slugify\b/);
  });

  it("exports shortUuid", () => {
    const src = readSource("features/runs/forkUtils.ts");
    expect(src).toMatch(/export\s+(function|const)\s+shortUuid\b/);
  });

  it("exports generateForkName", () => {
    const src = readSource("features/runs/forkUtils.ts");
    expect(src).toMatch(/export\s+(function|const)\s+generateForkName\b/);
  });
});

describe("slugify source-level contract (RUN-564 / AC3)", () => {
  it("slugify lowercases input (uses toLowerCase or equivalent)", () => {
    const src = readSource("features/runs/forkUtils.ts");
    expect(src).toMatch(/toLowerCase/);
  });

  it("slugify replaces spaces with hyphens", () => {
    const src = readSource("features/runs/forkUtils.ts");
    // Must contain a regex or replace that maps spaces to hyphens
    const handlesSpaces =
      src.includes("replace") &&
      (src.includes("/\\s+/") || src.includes("/ +/") || src.includes("\\s"));
    expect(handlesSpaces).toBe(true);
  });

  it("slugify strips non-alphanumeric characters", () => {
    const src = readSource("features/runs/forkUtils.ts");
    // Must have a regex that removes non-alphanumeric chars (except hyphens)
    expect(src).toMatch(/\[.*a-z.*0-9.*\]/);
  });
});

describe("shortUuid source-level contract (RUN-564 / AC3)", () => {
  it("shortUuid generates a 4-character result", () => {
    const src = readSource("features/runs/forkUtils.ts");
    // Must reference the length 4 constraint
    const has4Length =
      src.includes("4") &&
      (src.includes("slice") || src.includes("substring") || src.includes("length"));
    expect(has4Length).toBe(true);
  });

  it("shortUuid uses random generation (Math.random or crypto)", () => {
    const src = readSource("features/runs/forkUtils.ts");
    const usesRandom = src.includes("Math.random") || src.includes("crypto");
    expect(usesRandom).toBe(true);
  });
});

describe("generateForkName source-level contract (RUN-564 / AC3)", () => {
  it("generateForkName prefixes with 'drft-'", () => {
    const src = readSource("features/runs/forkUtils.ts");
    expect(src).toContain("drft-");
  });

  it("generateForkName calls slugify", () => {
    const src = readSource("features/runs/forkUtils.ts");
    expect(src).toMatch(/slugify\s*\(/);
  });

  it("generateForkName calls shortUuid", () => {
    const src = readSource("features/runs/forkUtils.ts");
    expect(src).toMatch(/shortUuid\s*\(/);
  });

  it("generateForkName assembles drft-{slug}-{uuid} pattern", () => {
    const src = readSource("features/runs/forkUtils.ts");
    // Must combine the prefix, slug, and uuid with hyphens
    // Pattern: template literal or concatenation with drft- prefix
    const hasTemplate =
      src.includes("`drft-") || src.includes('"drft-"') || src.includes("'drft-'");
    expect(hasTemplate).toBe(true);
  });
});

// ===========================================================================
// 2. Utility function runtime behavior (AC3)
// ===========================================================================

describe("slugify runtime behavior (RUN-564 / AC3)", () => {
  it("converts uppercase to lowercase", () => {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const mod = require("../forkUtils");
    expect(mod.slugify("Research Review")).toBe("research-review");
  });

  it("replaces spaces with hyphens", () => {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const mod = require("../forkUtils");
    expect(mod.slugify("my workflow name")).toBe("my-workflow-name");
  });

  it("strips non-alphanumeric characters except hyphens", () => {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const mod = require("../forkUtils");
    expect(mod.slugify("Test! @Workflow #1")).toBe("test-workflow-1");
  });

  it("collapses consecutive hyphens", () => {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const mod = require("../forkUtils");
    expect(mod.slugify("hello---world")).toBe("hello-world");
  });

  it("trims leading and trailing hyphens", () => {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const mod = require("../forkUtils");
    expect(mod.slugify("-hello-")).toBe("hello");
  });
});

describe("shortUuid runtime behavior (RUN-564 / AC3)", () => {
  it("returns a 4-character alphanumeric string", () => {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const mod = require("../forkUtils");
    const result = mod.shortUuid();
    expect(result).toHaveLength(4);
    expect(result).toMatch(/^[a-z0-9]{4}$/);
  });

  it("generates different values on successive calls", () => {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const mod = require("../forkUtils");
    const a = mod.shortUuid();
    const b = mod.shortUuid();
    expect(a).not.toBe(b);
  });
});

describe("generateForkName runtime behavior (RUN-564 / AC3)", () => {
  it("follows drft-{slug}-{uuid} convention", () => {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const mod = require("../forkUtils");
    const result = mod.generateForkName("Research & Review");
    expect(result).toMatch(/^drft-research-review-[a-z0-9]{4}$/);
  });

  it("handles single-word workflow names", () => {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const mod = require("../forkUtils");
    const result = mod.generateForkName("Pipeline");
    expect(result).toMatch(/^drft-pipeline-[a-z0-9]{4}$/);
  });

  it("matches the spec example format: drft-research-review-a7x3", () => {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const mod = require("../forkUtils");
    const result = mod.generateForkName("Research Review");
    // Must match drft-{base}-{4char}
    const parts = result.split("-");
    expect(parts[0]).toBe("drft");
    const suffix = parts[parts.length - 1];
    expect(suffix).toMatch(/^[a-z0-9]{4}$/);
    expect(result).toMatch(/^drft-research-review-/);
  });
});

// ===========================================================================
// 3. API layer — gitApi.getGitFile (AC2)
// ===========================================================================

describe("gitApi.getGitFile exists (RUN-564 / AC2)", () => {
  it("git.ts exports a getGitFile function", () => {
    const gitSrc = readSource("api/git.ts");
    expect(gitSrc).toMatch(/getGitFile/);
  });

  it("getGitFile calls GET /api/git/file with ref and path query params", () => {
    const gitSrc = readSource("api/git.ts");
    expect(gitSrc).toContain("/git/file");
  });

  it("getGitFile accepts ref (commit_sha) and path parameters", () => {
    const gitSrc = readSource("api/git.ts");
    // The function must reference both ref and path in its implementation
    const hasRefParam = gitSrc.includes("ref") && gitSrc.includes("path");
    expect(hasRefParam).toBe(true);
  });

  it("getGitFile returns an object with a content field (the YAML string)", () => {
    const gitSrc = readSource("api/git.ts");
    // Should have a zod schema or type that includes 'content' for the response
    const hasContentSchema = gitSrc.includes("content") && gitSrc.includes("getGitFile");
    expect(hasContentSchema).toBe(true);
  });
});

// ===========================================================================
// 4. Fork flow hook — useForkWorkflow (AC2, AC4)
// ===========================================================================

describe("useForkWorkflow hook exists (RUN-564 / AC2)", () => {
  it("useForkWorkflow is exported from a module", () => {
    const sources = [
      readSource("features/runs/useForkWorkflow.ts"),
      readSource("features/runs/useForkWorkflow.tsx"),
      readSource("hooks/useForkWorkflow.ts"),
      readSource("queries/runs.ts"),
    ].join("\n");

    expect(sources).toMatch(/export\s+(function|const)\s+useForkWorkflow\b/);
  });
});

describe("useForkWorkflow implements the fork flow (RUN-564 / AC2, AC4)", () => {
  it("calls gitApi.getGitFile to read the workflow YAML at the commit sha", () => {
    const sources = [
      readSource("features/runs/useForkWorkflow.ts"),
      readSource("features/runs/useForkWorkflow.tsx"),
      readSource("hooks/useForkWorkflow.ts"),
      readSource("queries/runs.ts"),
    ].join("\n");

    expect(sources).toMatch(/getGitFile|git.*file/i);
  });

  it("calls createWorkflow to persist the forked draft", () => {
    const sources = [
      readSource("features/runs/useForkWorkflow.ts"),
      readSource("features/runs/useForkWorkflow.tsx"),
      readSource("hooks/useForkWorkflow.ts"),
      readSource("queries/runs.ts"),
    ].join("\n");

    expect(sources).toMatch(/createWorkflow/);
  });

  it("sets enabled: false in the draft YAML (AC4)", () => {
    // Only check fork-specific files — not runs.ts which has unrelated "enabled" usage
    const sources = [
      readSource("features/runs/useForkWorkflow.ts"),
      readSource("features/runs/useForkWorkflow.tsx"),
      readSource("hooks/useForkWorkflow.ts"),
    ].join("\n");

    // The fork hook must explicitly set enabled: false on the draft
    const setsEnabledFalse =
      sources.includes("enabled: false") ||
      sources.includes("enabled:false") ||
      sources.includes("enabled, false");
    expect(setsEnabledFalse).toBe(true);
  });

  it("uses generateForkName for auto-naming the draft workflow", () => {
    const sources = [
      readSource("features/runs/useForkWorkflow.ts"),
      readSource("features/runs/useForkWorkflow.tsx"),
      readSource("hooks/useForkWorkflow.ts"),
      readSource("queries/runs.ts"),
    ].join("\n");

    expect(sources).toMatch(/generateForkName/);
  });

  it("navigates to /workflows/:newId/edit after successful fork", () => {
    const sources = [
      readSource("features/runs/useForkWorkflow.ts"),
      readSource("features/runs/useForkWorkflow.tsx"),
      readSource("hooks/useForkWorkflow.ts"),
      readSource("queries/runs.ts"),
    ].join("\n");

    expect(sources).toMatch(/\/workflows\/.*\/edit/);
  });

  it("uses yaml parse/stringify to modify the document", () => {
    const sources = [
      readSource("features/runs/useForkWorkflow.ts"),
      readSource("features/runs/useForkWorkflow.tsx"),
      readSource("hooks/useForkWorkflow.ts"),
      readSource("features/runs/RunDetailHeader.tsx"),
    ].join("\n");

    const usesYaml = sources.includes("yaml") || sources.includes("YAML");
    expect(usesYaml).toBe(true);
  });
});

// ===========================================================================
// 5. Component integration — Fork button visibility (AC1)
// ===========================================================================

describe("Fork button is visible in RunDetailHeader (RUN-564 / AC1)", () => {
  it("renders a Fork button for completed runs", () => {
    renderHeader({ status: "completed" });
    const forkBtn = screen.getByRole("button", { name: /fork/i });
    expect(forkBtn).toBeTruthy();
  });

  it("renders a Fork button for failed runs", () => {
    renderHeader({ status: "failed" });
    const forkBtn = screen.getByRole("button", { name: /fork/i });
    expect(forkBtn).toBeTruthy();
  });

  it("renders a Fork button for error runs", () => {
    renderHeader({ status: "error" });
    const forkBtn = screen.getByRole("button", { name: /fork/i });
    expect(forkBtn).toBeTruthy();
  });

  it("RunDetailHeader source imports fork-related functionality", () => {
    const headerSrc = readSource("features/runs/RunDetailHeader.tsx");
    expect(headerSrc).toMatch(/[Ff]ork/);
  });
});

// ===========================================================================
// 6. Fork button click triggers full flow (AC2)
// ===========================================================================

describe("Fork button click triggers the full fork flow (RUN-564 / AC2)", () => {
  it("clicking fork on a completed run with commit_sha initiates the fork flow", async () => {
    const { user } = renderHeader({ status: "completed", commitSha: "abc123" });

    const forkBtn = screen.getByRole("button", { name: /fork/i });
    await user.click(forkBtn);

    // After click, the button should enter a loading state with "Forking..." text
    await waitFor(() => {
      const loadingText = screen.queryByText(/forking/i);
      expect(loadingText).toBeTruthy();
    });
  });

  it("after successful fork, navigates to /workflows/:newId/edit", async () => {
    const { router, user } = renderHeader({ status: "completed", commitSha: "abc123" });

    const forkBtn = screen.getByRole("button", { name: /fork/i });
    await user.click(forkBtn);

    await waitFor(() => {
      expect(router.state.location.pathname).toMatch(/^\/workflows\/.*\/edit$/);
    });
  });
});

// ===========================================================================
// 7. Fork button disabled during active execution (AC5)
// ===========================================================================

describe("Fork button disabled during active execution (RUN-564 / AC5)", () => {
  it("fork button is disabled when status is running", () => {
    renderHeader({ status: "running", commitSha: "abc123" });
    const forkBtn = screen.getByRole("button", { name: /fork/i });
    expect(
      forkBtn.hasAttribute("disabled") ||
        forkBtn.getAttribute("aria-disabled") === "true",
    ).toBe(true);
  });

  it("fork button is disabled when status is pending", () => {
    renderHeader({ status: "pending", commitSha: "abc123" });
    const forkBtn = screen.getByRole("button", { name: /fork/i });
    expect(
      forkBtn.hasAttribute("disabled") ||
        forkBtn.getAttribute("aria-disabled") === "true",
    ).toBe(true);
  });

  it("shows tooltip 'Wait for the run to finish before forking' when running", async () => {
    const { user } = renderHeader({ status: "running", commitSha: "abc123" });

    const forkBtn = screen.getByRole("button", { name: /fork/i });
    await user.hover(forkBtn);

    await waitFor(() => {
      const tooltip = screen.getByText(/wait for the run to finish/i);
      expect(tooltip).toBeTruthy();
    });
  });
});

// ===========================================================================
// 8. Fork button disabled when snapshot unavailable (AC6)
// ===========================================================================

describe("Fork button disabled when snapshot unavailable (RUN-564 / AC6)", () => {
  it("fork button is disabled when commit_sha is null", () => {
    renderHeader({ status: "completed", commitSha: null });
    const forkBtn = screen.getByRole("button", { name: /fork/i });
    expect(
      forkBtn.hasAttribute("disabled") ||
        forkBtn.getAttribute("aria-disabled") === "true",
    ).toBe(true);
  });

  it("fork button is disabled when commit_sha is undefined", () => {
    renderHeader({
      status: "completed",
      commitSha: undefined as unknown as null,
    });
    const forkBtn = screen.getByRole("button", { name: /fork/i });
    expect(
      forkBtn.hasAttribute("disabled") ||
        forkBtn.getAttribute("aria-disabled") === "true",
    ).toBe(true);
  });

  it("shows tooltip 'Snapshot unavailable' when no commit_sha", async () => {
    const { user } = renderHeader({ status: "completed", commitSha: null });

    const forkBtn = screen.getByRole("button", { name: /fork/i });
    await user.hover(forkBtn);

    await waitFor(() => {
      const tooltip = screen.getByText(/snapshot unavailable/i);
      expect(tooltip).toBeTruthy();
    });
  });
});

// ===========================================================================
// 9. Fork button enabled for terminal statuses with valid commit_sha
// ===========================================================================

describe("Fork button enabled for terminal statuses (RUN-564 / AC1)", () => {
  it("fork button is NOT disabled when completed with commit_sha", () => {
    renderHeader({ status: "completed", commitSha: "abc123" });
    const forkBtn = screen.getByRole("button", { name: /fork/i });
    expect(forkBtn.hasAttribute("disabled")).toBe(false);
  });

  it("fork button is NOT disabled when failed with commit_sha", () => {
    renderHeader({ status: "failed", commitSha: "abc123" });
    const forkBtn = screen.getByRole("button", { name: /fork/i });
    expect(forkBtn.hasAttribute("disabled")).toBe(false);
  });
});

// ===========================================================================
// 10. Error handling — toast and button re-enable (AC7)
// ===========================================================================

describe("Error handling — toast and button re-enable (RUN-564 / AC7)", () => {
  it("fork source contains error toast: 'Couldn\\'t create fork. Try again.'", () => {
    const headerSrc = readSource("features/runs/RunDetailHeader.tsx");
    const hookSources = [
      readSource("features/runs/useForkWorkflow.ts"),
      readSource("features/runs/useForkWorkflow.tsx"),
      readSource("hooks/useForkWorkflow.ts"),
      readSource("queries/runs.ts"),
    ].join("\n");

    const combined = headerSrc + hookSources;
    expect(combined).toMatch(/Couldn.*create fork|couldn.*create fork/i);
  });

  it("fork flow has error handling that resets loading state", () => {
    const headerSrc = readSource("features/runs/RunDetailHeader.tsx");
    const hookSources = [
      readSource("features/runs/useForkWorkflow.ts"),
      readSource("features/runs/useForkWorkflow.tsx"),
      readSource("hooks/useForkWorkflow.ts"),
    ].join("\n");

    const combined = headerSrc + hookSources;

    // Must have error handling (catch/onError) that resets isForking/loading state
    const hasErrorHandling =
      combined.includes("catch") || combined.includes("onError");
    const hasStateReset =
      combined.includes("setIsForking(false)") ||
      combined.includes("isForking") ||
      combined.includes("isPending") ||
      combined.includes("setLoading(false)");

    expect(hasErrorHandling).toBe(true);
    expect(hasStateReset).toBe(true);
  });
});

// ===========================================================================
// 11. No fork info banner (AC8)
// ===========================================================================

describe("No fork info banner (RUN-564 / AC8)", () => {
  it("RunDetailHeader does NOT render a fork info banner", () => {
    renderHeader({ status: "completed", commitSha: "abc123" });
    const banner = screen.queryByText(/forked from/i);
    expect(banner).toBeNull();
  });

  it("RunDetail does NOT render a fork info banner", () => {
    const detailSrc = readSource("features/runs/RunDetail.tsx");
    const headerSrc = readSource("features/runs/RunDetailHeader.tsx");
    const combined = detailSrc + headerSrc;
    expect(combined).not.toMatch(/fork.*banner|forked.*from.*banner/i);
  });
});

// ===========================================================================
// 12. Fork button loading state label (AC2)
// ===========================================================================

describe("Fork button loading state (RUN-564 / AC2)", () => {
  it("RunDetailHeader source contains 'Forking' loading label", () => {
    const src = readSource("features/runs/RunDetailHeader.tsx");
    expect(src).toMatch(/[Ff]orking/);
  });

  it("RunDetailHeader source contains the idle 'Fork' button label", () => {
    const src = readSource("features/runs/RunDetailHeader.tsx");
    // Must have a distinct "Fork" text for the button
    expect(src).toMatch(/>\s*Fork\s*</);
  });
});

// ===========================================================================
// 13. RunDetailHeader uses commit_sha and status for fork gating
// ===========================================================================

describe("RunDetailHeader handles commit_sha and status for fork (RUN-564)", () => {
  it("RunDetailHeader source references commit_sha", () => {
    const src = readSource("features/runs/RunDetailHeader.tsx");
    expect(src).toMatch(/commit_sha/);
  });

  it("RunDetailHeader checks for running status to disable fork", () => {
    const src = readSource("features/runs/RunDetailHeader.tsx");
    const checksRunning =
      src.includes('"running"') || src.includes("'running'");
    expect(checksRunning).toBe(true);
  });

  it("RunDetailHeader checks for pending status to disable fork", () => {
    const src = readSource("features/runs/RunDetailHeader.tsx");
    const checksPending =
      src.includes('"pending"') || src.includes("'pending'");
    expect(checksPending).toBe(true);
  });
});
