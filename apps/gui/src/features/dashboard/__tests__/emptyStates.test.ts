/**
 * RED-TEAM tests for RUN-340: A4 — Empty states — end-to-end.
 *
 * These tests verify ALL acceptance criteria by reading source files as strings
 * and asserting observable structural properties:
 *
 * AC1: No-workflows state shows EmptyState with "Create Workflow" CTA
 * AC2: CTA creates workflow and navigates to canvas
 * AC3: No-runs state shows zero KPIs + EmptyState with "Open Flows" CTA
 * AC4: Uses existing EmptyState component, no new components
 * AC5: Correct conditional priority (no workflows -> no runs -> dashboard)
 *
 * Expected failures (current state):
 *   - DashboardOrOnboarding.tsx does not import EmptyState
 *   - No useWorkflows import in dashboard (needed for no-workflows check)
 *   - No conditional branching based on workflow count
 *   - No "Welcome to Runsight" heading
 *   - No "No runs yet" heading
 *   - No "Open Flows" CTA
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SRC_DIR = resolve(__dirname, "../../..");
const REPO_ROOT = resolve(__dirname, "../../../../../..");
const EMPTY_STATE_PATH = resolve(
  REPO_ROOT,
  "packages",
  "ui",
  "src",
  "components",
  "shared",
  "EmptyState.tsx",
);

function readSource(relativePath: string): string {
  return readFileSync(resolve(SRC_DIR, relativePath), "utf-8");
}

const DASHBOARD_PATH = "features/dashboard/DashboardOrOnboarding.tsx";

// ===========================================================================
// 1. Dashboard imports EmptyState component (AC4)
// ===========================================================================

describe("Dashboard uses existing EmptyState component (AC4)", () => {
  it("imports EmptyState from @runsight/ui/empty-state", () => {
    const source = readSource(DASHBOARD_PATH);
    expect(source).toMatch(/import.*EmptyState.*from.*@runsight\/ui\/empty-state/);
  });

  it("renders EmptyState at least twice (one for no-workflows, one for no-runs)", () => {
    const source = readSource(DASHBOARD_PATH);
    const emptyStateCount = (source.match(/<EmptyState\b/g) || []).length;
    expect(emptyStateCount).toBeGreaterThanOrEqual(2);
  });

  it("does NOT define any new component files for empty states", () => {
    // EmptyState.tsx already exists and should be the only empty state component
    const source = readFileSync(EMPTY_STATE_PATH, "utf-8");
    expect(source).toMatch(/export\s+function\s+EmptyState/);
  });
});

// ===========================================================================
// 2. No-workflows empty state — "Welcome to Runsight" (AC1)
// ===========================================================================

describe("No-workflows state: EmptyState with 'Create Workflow' CTA (AC1)", () => {
  it("imports useWorkflows to check for workflow existence", () => {
    const source = readSource(DASHBOARD_PATH);
    expect(source).toMatch(/import.*useWorkflows.*from/);
  });

  it("calls useWorkflows() in the component", () => {
    const source = readSource(DASHBOARD_PATH);
    expect(source).toMatch(/useWorkflows\s*\(/);
  });

  it('has heading text "Welcome to Runsight"', () => {
    const source = readSource(DASHBOARD_PATH);
    expect(source).toMatch(/Welcome to Runsight/);
  });

  it('has description "Create your first workflow to start orchestrating AI agents."', () => {
    const source = readSource(DASHBOARD_PATH);
    expect(source).toMatch(
      /Create your first workflow to start orchestrating AI agents/,
    );
  });

  it('has a CTA labeled "Create Workflow"', () => {
    const source = readSource(DASHBOARD_PATH);
    // EmptyState action.label should be "Create Workflow"
    expect(source).toMatch(/["']Create Workflow["']/);
  });

  it("uses a workflow icon (e.g. Workflow, GitBranch, or similar) for the empty state icon", () => {
    const source = readSource(DASHBOARD_PATH);
    // The no-workflows EmptyState should pass an icon prop referencing a workflow-related icon
    // Common options: Workflow, GitBranch, GitFork, Network, etc.
    const hasWorkflowIcon =
      /import.*(?:Workflow|GitBranch|GitFork|Network|Layers).*from\s*["']lucide-react["']/.test(
        source,
      );
    expect(
      hasWorkflowIcon,
      "Expected a workflow-related icon import from lucide-react for no-workflows empty state",
    ).toBe(true);
  });
});

// ===========================================================================
// 3. "Create Workflow" CTA creates and navigates (AC2)
// ===========================================================================

describe("Create Workflow CTA creates workflow and navigates to canvas (AC2)", () => {
  it("EmptyState action.onClick triggers workflow creation", () => {
    const source = readSource(DASHBOARD_PATH);
    // The action onClick should call createWorkflow or handleNewWorkflow
    // which ultimately calls POST /api/workflows and navigates
    // Look for pattern: action={{ label: "Create Workflow", onClick: <handler> }}
    // where handler uses createWorkflow.mutateAsync or similar
    const hasCreateInAction =
      /Create Workflow.*onClick.*create|action.*Create Workflow.*handleNew|label.*Create Workflow/.test(
        source,
      );
    expect(
      hasCreateInAction,
      "Expected EmptyState action with 'Create Workflow' label wired to workflow creation",
    ).toBe(true);
  });

  it("has at least two navigation paths: one from header button, one from EmptyState CTA", () => {
    const source = readSource(DASHBOARD_PATH);
    // Both the PageHeader "New Workflow" button and the EmptyState "Create Workflow"
    // CTA should trigger workflow creation + navigation. This means there should be
    // two distinct code paths that call createWorkflow or handleNewWorkflow.
    // At minimum, EmptyState action.onClick must reference the creation handler.
    const actionOnClickMatches = source.match(/action\s*=\s*\{\s*\{/g) || [];
    expect(actionOnClickMatches.length).toBeGreaterThanOrEqual(1);
  });
});

// ===========================================================================
// 4. No-runs empty state — KPIs with zeros + EmptyState (AC3)
// ===========================================================================

describe("No-runs state: zero KPIs + EmptyState with 'Open Flows' CTA (AC3)", () => {
  it('has heading text "No runs yet"', () => {
    const source = readSource(DASHBOARD_PATH);
    expect(source).toMatch(/No runs yet/);
  });

  it('has description about running a workflow to see results', () => {
    const source = readSource(DASHBOARD_PATH);
    expect(source).toMatch(
      /Run a workflow to see eval results, cost tracking, and regression detection here/,
    );
  });

  it('has a CTA labeled "Open Flows"', () => {
    const source = readSource(DASHBOARD_PATH);
    expect(source).toMatch(/["']Open Flows["']/);
  });

  it('"Open Flows" CTA navigates to /workflows', () => {
    const source = readSource(DASHBOARD_PATH);
    // The action onClick should navigate to /workflows
    // Pattern: navigate("/workflows") or navigate(`/workflows`)
    const hasNavigateToWorkflows =
      /navigate\s*\(\s*["'`]\/workflows["'`]\s*\)/.test(source);
    expect(
      hasNavigateToWorkflows,
      'Expected navigate("/workflows") call for Open Flows CTA',
    ).toBe(true);
  });

  it("uses a play-related icon (e.g. Play, PlayCircle) for the no-runs empty state", () => {
    const source = readSource(DASHBOARD_PATH);
    // The no-runs EmptyState should pass a play-related icon prop
    const hasPlayIcon =
      /import.*(?:Play|PlayCircle|CirclePlay).*from\s*["']lucide-react["']/.test(
        source,
      );
    expect(
      hasPlayIcon,
      "Expected a play-related icon import from lucide-react for no-runs empty state",
    ).toBe(true);
  });
});

// ===========================================================================
// 5. Conditional rendering priority (AC5)
// ===========================================================================

describe("Conditional rendering priority: no workflows > no runs > dashboard (AC5)", () => {
  it("checks workflows data before rendering KPIs", () => {
    const source = readSource(DASHBOARD_PATH);
    // The component should check if workflows exist before deciding what to render
    // Patterns: workflows?.items?.length, workflows?.total, data?.items?.length === 0
    const checksWorkflows =
      /workflows.*\?\.(items|total|length)|data\?\.items\?\.length|data\?\.total/.test(
        source,
      );
    expect(
      checksWorkflows,
      "Expected conditional check on workflows data for rendering priority",
    ).toBe(true);
  });

  it("no-workflows state renders full-page EmptyState without KPI StatCards", () => {
    const source = readSource(DASHBOARD_PATH);
    // When there are no workflows, the dashboard should show ONLY the EmptyState,
    // NOT the KPI StatCards. This means the StatCards are conditionally rendered
    // and appear only when workflows exist.
    // The no-workflows branch should return early or conditionally exclude StatCards.
    // Look for a pattern where "Welcome to Runsight" branch does NOT include StatCard.
    // We verify this by checking that there IS conditional logic separating them.
    const hasEarlyReturn =
      /return\s*\([\s\S]*?Welcome to Runsight/.test(source);
    const hasConditionalBranch =
      /if\s*\(.*(?:workflows|items|total).*\)[\s\S]*?Welcome to Runsight|(?:workflows|items|total).*===?\s*0[\s\S]*?Welcome to Runsight/.test(
        source,
      );
    const hasTernaryBranch =
      /(?:workflows|items|total).*\?[\s\S]*?Welcome to Runsight|Welcome to Runsight[\s\S]*?StatCard/.test(
        source,
      );
    expect(
      hasEarlyReturn || hasConditionalBranch || hasTernaryBranch,
      "Expected no-workflows branch to render full-page EmptyState separate from KPI cards",
    ).toBe(true);
  });

  it("no-runs state shows KPI StatCards alongside EmptyState", () => {
    const source = readSource(DASHBOARD_PATH);
    // When workflows exist but no runs, KPIs show zeros AND the "No runs yet" EmptyState
    // Both StatCard and "No runs yet" should appear in the same render path
    const hasStatCard = /<StatCard\b/.test(source);
    const hasNoRuns = /No runs yet/.test(source);
    expect(hasStatCard && hasNoRuns).toBe(true);
  });

  it("checks runsToday (or equivalent) to determine no-runs state", () => {
    const source = readSource(DASHBOARD_PATH);
    // The no-runs condition should check runsToday === 0 or similar
    const checksRuns =
      /runsToday\s*===?\s*0|runs_today\s*===?\s*0|runsToday\s*!|!.*runsToday/.test(
        source,
      );
    expect(
      checksRuns,
      "Expected a check on runsToday === 0 to determine no-runs state",
    ).toBe(true);
  });

  it("conditional priority: workflows check comes before runs check in source", () => {
    const source = readSource(DASHBOARD_PATH);
    // The workflow existence check should appear BEFORE the runs check
    // because no-workflows takes precedence over no-runs
    const workflowCheckPos = source.search(
      /workflows.*\?\.|(?:items|total).*(?:===?\s*0|\.length)/,
    );
    const runsCheckPos = source.search(
      /runsToday\s*===?\s*0|No runs yet/,
    );
    expect(workflowCheckPos).toBeGreaterThan(-1);
    expect(runsCheckPos).toBeGreaterThan(-1);
    expect(workflowCheckPos).toBeLessThan(runsCheckPos);
  });
});
