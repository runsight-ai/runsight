/**
 * RED-TEAM tests for RUN-337: A1 — Gut dashboard monolith + nav sidebar cleanup.
 *
 * These tests verify ALL acceptance criteria by reading source files as strings
 * and asserting observable structural properties:
 *
 * AC1: Dashboard page renders with PageHeader ("Home" + "New Workflow" button) and empty content area
 * AC2: Nav sidebar shows: Home, Flows, Souls, Settings — nothing else
 * AC3: Header height matches --header-height (40px)
 * AC4: Status bar height matches --status-bar-height (22px)
 * AC5: Sidebar hover uses CSS, not imperative JS
 * AC6: "New Workflow" button creates workflow and navigates to canvas
 * AC7: Zero phantom field accesses on WorkflowResponse
 * AC8: App compiles and routes work (verified structurally)
 *
 * Expected failures (current state):
 *   - DashboardOrOnboarding.tsx is a 465-line monolith with phantom fields
 *   - ShellLayout.tsx has Tasks, Steps, Runs nav items; uses h-12/h-7; uses imperative hover
 *   - Dashboard title says "Dashboard" not "Home"; workflows label says "Workflows" not "Flows"
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

function countLines(source: string): number {
  return source.split("\n").length;
}

// ---------------------------------------------------------------------------
// File paths
// ---------------------------------------------------------------------------

const DASHBOARD_PATH = "features/dashboard/DashboardOrOnboarding.tsx";
const SHELL_LAYOUT_PATH = "routes/layouts/ShellLayout.tsx";
const API_DASHBOARD_PATH = "api/dashboard.ts";

// ===========================================================================
// 1. Dashboard — gut the monolith (AC1, AC7)
// ===========================================================================

describe("Dashboard page shell (AC1: PageHeader + empty content)", () => {
  let source: string;

  it("DashboardOrOnboarding.tsx is under 80 lines (gutted from 465)", () => {
    source = readSource(DASHBOARD_PATH);
    const lines = countLines(source);
    expect(lines).toBeLessThanOrEqual(80);
  });

  it("imports PageHeader component", () => {
    source = readSource(DASHBOARD_PATH);
    expect(source).toMatch(/import.*PageHeader.*from/);
  });

  it("renders PageHeader with title 'Home'", () => {
    source = readSource(DASHBOARD_PATH);
    // The PageHeader should receive title="Home"
    expect(source).toMatch(/PageHeader/);
    expect(source).toMatch(/title\s*=\s*["']Home["']/);
  });

  it("has a 'New Workflow' button in PageHeader actions", () => {
    source = readSource(DASHBOARD_PATH);
    // Should have a Button with text "New Workflow" wired as PageHeader actions
    expect(source).toMatch(/New Workflow/);
    expect(source).toMatch(/actions\s*=/);
  });

  it("does NOT render Quick Actions row", () => {
    source = readSource(DASHBOARD_PATH);
    expect(source).not.toMatch(/Quick Actions/i);
    expect(source).not.toMatch(/Generate with AI/);
    expect(source).not.toMatch(/Import YAML/);
  });

  it("does NOT render System Health bar", () => {
    source = readSource(DASHBOARD_PATH);
    expect(source).not.toMatch(/System Health/i);
    expect(source).not.toMatch(/All Systems Operational/);
  });

  it("does NOT render Active Workflows table", () => {
    source = readSource(DASHBOARD_PATH);
    expect(source).not.toMatch(/Active Workflows/);
    expect(source).not.toMatch(/DataTable/);
  });

  it("does NOT render Recent Runs grid", () => {
    source = readSource(DASHBOARD_PATH);
    expect(source).not.toMatch(/Recent Runs/);
  });

  it("does NOT render Summary Cards (Active Runs, Completed, Total Cost, etc.)", () => {
    source = readSource(DASHBOARD_PATH);
    expect(source).not.toMatch(/Active Runs/);
    expect(source).not.toMatch(/Completed/);
    expect(source).not.toMatch(/Total Cost/);
  });

  it("does NOT render the onboarding 'Create your first workflow' card", () => {
    source = readSource(DASHBOARD_PATH);
    expect(source).not.toMatch(/Create your first workflow/);
  });

  it("does NOT import dashboard query hooks (useDashboardSummary, useRecentRuns)", () => {
    source = readSource(DASHBOARD_PATH);
    expect(source).not.toMatch(/useDashboardSummary/);
    expect(source).not.toMatch(/useRecentRuns/);
  });

  it("does NOT have a PopulatedDashboard function", () => {
    source = readSource(DASHBOARD_PATH);
    expect(source).not.toMatch(/function PopulatedDashboard/);
  });
});

// ===========================================================================
// 2. Zero phantom field accesses on WorkflowResponse (AC7)
// ===========================================================================

describe("No phantom WorkflowResponse field accesses (AC7)", () => {
  let source: string;

  // These fields do NOT exist on the generated WorkflowResponse schema:
  //   status, updated_at, created_at, last_run_duration, last_run_cost_usd,
  //   last_run_completed_at, step_count, block_count

  it("does NOT access workflow.status", () => {
    source = readSource(DASHBOARD_PATH);
    expect(source).not.toMatch(/workflow\.status/);
  });

  it("does NOT access workflow.updated_at", () => {
    source = readSource(DASHBOARD_PATH);
    expect(source).not.toMatch(/workflow\.updated_at/);
  });

  it("does NOT access workflow.created_at", () => {
    source = readSource(DASHBOARD_PATH);
    expect(source).not.toMatch(/workflow\.created_at/);
  });

  it("does NOT access workflow.last_run_duration", () => {
    source = readSource(DASHBOARD_PATH);
    expect(source).not.toMatch(/workflow\.last_run_duration/);
  });

  it("does NOT access workflow.last_run_cost_usd", () => {
    source = readSource(DASHBOARD_PATH);
    expect(source).not.toMatch(/workflow\.last_run_cost_usd/);
  });

  it("does NOT access workflow.last_run_completed_at", () => {
    source = readSource(DASHBOARD_PATH);
    expect(source).not.toMatch(/workflow\.last_run_completed_at/);
  });

  it("does NOT access workflow.step_count", () => {
    source = readSource(DASHBOARD_PATH);
    expect(source).not.toMatch(/workflow\.step_count/);
  });

  it("does NOT access workflow.block_count", () => {
    source = readSource(DASHBOARD_PATH);
    expect(source).not.toMatch(/workflow\.block_count/);
  });
});

// ===========================================================================
// 3. "New Workflow" button behavior (AC6)
// ===========================================================================

describe("New Workflow button wiring (AC6)", () => {
  let source: string;

  it("imports useCreateWorkflow or calls POST /api/workflows", () => {
    source = readSource(DASHBOARD_PATH);
    // Should use either the mutation hook or a direct API call
    const usesHook = /useCreateWorkflow/.test(source);
    const usesApi = /workflowsApi\.createWorkflow|api\.post.*\/workflows/.test(source);
    expect(
      usesHook || usesApi,
      "Expected useCreateWorkflow hook or direct POST /api/workflows call",
    ).toBe(true);
  });

  it("imports useNavigate for post-creation navigation", () => {
    source = readSource(DASHBOARD_PATH);
    expect(source).toMatch(/useNavigate/);
  });

  it("navigates to /workflows/:id/edit after creation", () => {
    source = readSource(DASHBOARD_PATH);
    // Should navigate to the edit route for the created workflow
    // Patterns like: navigate(`/workflows/${id}/edit`) or navigate(`/workflows/${result.id}/edit`)
    expect(source).toMatch(/\/workflows\/.*\/edit/);
  });

  it("does NOT use NewWorkflowModal (button directly creates and navigates)", () => {
    source = readSource(DASHBOARD_PATH);
    // The old approach used a modal; the new approach should wire the button directly
    expect(source).not.toMatch(/NewWorkflowModal/);
  });
});

// ===========================================================================
// 4. Nav sidebar — items (AC2)
// ===========================================================================

describe("Nav sidebar items (AC2: Home, Flows, Souls, Settings only)", () => {
  let source: string;

  it("has a nav item labeled 'Home' (renamed from 'Dashboard')", () => {
    source = readSource(SHELL_LAYOUT_PATH);
    // Should have label: "Home" in NAV_ITEMS
    expect(source).toMatch(/label:\s*["']Home["']/);
  });

  it("has a nav item labeled 'Flows' (renamed from 'Workflows')", () => {
    source = readSource(SHELL_LAYOUT_PATH);
    expect(source).toMatch(/label:\s*["']Flows["']/);
  });

  it("has a nav item labeled 'Souls'", () => {
    source = readSource(SHELL_LAYOUT_PATH);
    expect(source).toMatch(/label:\s*["']Souls["']/);
  });

  it("has a nav item labeled 'Settings'", () => {
    source = readSource(SHELL_LAYOUT_PATH);
    expect(source).toMatch(/label:\s*["']Settings["']/);
  });

  it("does NOT have a nav item labeled 'Dashboard'", () => {
    source = readSource(SHELL_LAYOUT_PATH);
    expect(source).not.toMatch(/label:\s*["']Dashboard["']/);
  });

  it("does NOT have a nav item labeled 'Workflows'", () => {
    source = readSource(SHELL_LAYOUT_PATH);
    expect(source).not.toMatch(/label:\s*["']Workflows["']/);
  });

  it("does NOT have a nav item labeled 'Tasks'", () => {
    source = readSource(SHELL_LAYOUT_PATH);
    expect(source).not.toMatch(/label:\s*["']Tasks["']/);
  });

  it("does NOT have a nav item labeled 'Steps'", () => {
    source = readSource(SHELL_LAYOUT_PATH);
    expect(source).not.toMatch(/label:\s*["']Steps["']/);
  });

  it("does NOT have a nav item labeled 'Runs'", () => {
    source = readSource(SHELL_LAYOUT_PATH);
    expect(source).not.toMatch(/label:\s*["']Runs["']/);
  });

  it("does NOT import removed icons (ListTodo, CheckSquare, Play)", () => {
    source = readSource(SHELL_LAYOUT_PATH);
    expect(source).not.toMatch(/ListTodo/);
    expect(source).not.toMatch(/CheckSquare/);
    // Play icon for Runs nav item should be gone
    // Be careful: Play could be used elsewhere, but it was only used for the Runs nav item
    expect(source).not.toMatch(/\bPlay\b/);
  });

  it("NAV_ITEMS + BOTTOM_NAV total exactly 4 entries", () => {
    source = readSource(SHELL_LAYOUT_PATH);
    // Count the objects in NAV_ITEMS and BOTTOM_NAV arrays
    // NAV_ITEMS should have: Home, Flows, Souls (3 items)
    // BOTTOM_NAV should have: Settings (1 item)
    // Total: 4
    const navItemMatches = source.match(/\{\s*to:\s*["'][^"']+["'],\s*icon:/g);
    expect(navItemMatches).not.toBeNull();
    expect(navItemMatches!.length).toBe(4);
  });
});

// ===========================================================================
// 5. Header height uses --header-height token (AC3)
// ===========================================================================

describe("Header height uses --header-height (AC3)", () => {
  let source: string;

  it("header uses h-[var(--header-height)] instead of h-12", () => {
    source = readSource(SHELL_LAYOUT_PATH);
    // The header element should use the CSS variable
    expect(source).toMatch(/h-\[var\(--header-height\)\]/);
  });

  it("header does NOT use hardcoded h-12", () => {
    source = readSource(SHELL_LAYOUT_PATH);
    // There should be no h-12 remaining for the header
    // Note: h-12 could appear in other contexts (e.g. sidebar logo area),
    // so we check that the main header specifically doesn't use it.
    // The header element is identified by the <header> tag in the main content area.
    // Since the sidebar logo div also uses h-12, we check that the total count of h-12 is 0.
    expect(source).not.toMatch(/\bh-12\b/);
  });

  it("sidebar logo area also uses h-[var(--header-height)]", () => {
    source = readSource(SHELL_LAYOUT_PATH);
    // Both the sidebar logo row and the main header should align using the same token
    // Count occurrences of the token class
    const matches = source.match(/h-\[var\(--header-height\)\]/g);
    expect(matches).not.toBeNull();
    expect(matches!.length).toBeGreaterThanOrEqual(2);
  });
});

// ===========================================================================
// 6. Status bar height uses --status-bar-height token (AC4)
// ===========================================================================

describe("Status bar height uses --status-bar-height (AC4)", () => {
  let source: string;

  it("status bar uses h-[var(--status-bar-height)] instead of h-7", () => {
    source = readSource(SHELL_LAYOUT_PATH);
    expect(source).toMatch(/h-\[var\(--status-bar-height\)\]/);
  });

  it("status bar does NOT use hardcoded h-7", () => {
    source = readSource(SHELL_LAYOUT_PATH);
    expect(source).not.toMatch(/\bh-7\b/);
  });
});

// ===========================================================================
// 7. Sidebar hover uses CSS, not imperative JS (AC5)
// ===========================================================================

describe("Sidebar hover uses CSS, not imperative JS (AC5)", () => {
  let source: string;

  it("does NOT use onMouseEnter handlers", () => {
    source = readSource(SHELL_LAYOUT_PATH);
    expect(source).not.toMatch(/onMouseEnter/);
  });

  it("does NOT use onMouseLeave handlers", () => {
    source = readSource(SHELL_LAYOUT_PATH);
    expect(source).not.toMatch(/onMouseLeave/);
  });

  it("does NOT use imperative style.backgroundColor assignments", () => {
    source = readSource(SHELL_LAYOUT_PATH);
    expect(source).not.toMatch(/\.style\.backgroundColor\s*=/);
  });

  it("uses CSS hover class for sidebar nav items (hover:bg-[var(--sidebar-hover)])", () => {
    source = readSource(SHELL_LAYOUT_PATH);
    expect(source).toMatch(/hover:bg-\[var\(--sidebar-hover\)\]/);
  });
});

// ===========================================================================
// 8. API dashboard cleanup (AC8)
// ===========================================================================

describe("API dashboard cleanup", () => {
  it("api/dashboard.ts is either removed or properly wired", () => {
    // After gutting the dashboard, the dashboard API fetcher should either:
    // - Be deleted (file doesn't exist)
    // - Or be simplified/kept only if still referenced
    //
    // The dashboard no longer needs useDashboardSummary or useRecentRuns,
    // so the query hooks file should not reference them or they should be removed.
    const dashSource = readSource(DASHBOARD_PATH);

    // Dashboard should NOT import from queries/dashboard anymore
    expect(dashSource).not.toMatch(/from\s*["']@\/queries\/dashboard["']/);
    expect(dashSource).not.toMatch(/from\s*["'].*queries\/dashboard["']/);
  });
});

// ===========================================================================
// 9. Flows route stays at /workflows (AC2 detail)
// ===========================================================================

describe("Flows route path preserved", () => {
  it("'Flows' nav item routes to /workflows (route unchanged)", () => {
    const source = readSource(SHELL_LAYOUT_PATH);
    // The nav item labeled "Flows" should still route to "/workflows"
    // Pattern: { to: "/workflows", ..., label: "Flows" }
    expect(source).toMatch(/to:\s*["']\/workflows["']/);
    expect(source).toMatch(/label:\s*["']Flows["']/);
  });
});
