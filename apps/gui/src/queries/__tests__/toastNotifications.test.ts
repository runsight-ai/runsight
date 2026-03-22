/**
 * RED-TEAM tests for RUN-240: Toast notifications for all mutation operations.
 *
 * These tests verify that every mutation hook in the query layer calls:
 * 1. toast.success(...) in its onSuccess callback
 * 2. toast.error(...) in its onError callback
 * 3. The toast import from "sonner" exists in each file
 *
 * Approach: Source-level analysis (same pattern as runDetailPolling.test.ts).
 * We read each query file and assert that mutation functions contain toast calls.
 *
 * All 25 mutations across 7 files (+ 1 component handler) must have both
 * success and error toasts. Currently NONE of them do -- these tests should
 * all FAIL.
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "fs";
import { resolve } from "path";

// ---------------------------------------------------------------------------
// Helper: extract a named function body from source code
// ---------------------------------------------------------------------------

/**
 * Extracts the full body of an `export function <name>(...)` from source.
 * Uses brace-depth tracking to find the matching closing brace.
 * Returns "" if the function is not found.
 */
function extractFunction(source: string, name: string): string {
  const startIdx = source.indexOf(`function ${name}`);
  if (startIdx === -1) return "";
  let depth = 0;
  let bodyStart = -1;
  for (let i = startIdx; i < source.length; i++) {
    if (source[i] === "{") {
      if (bodyStart === -1) bodyStart = i;
      depth++;
    } else if (source[i] === "}") {
      depth--;
      if (depth === 0) return source.slice(bodyStart, i + 1);
    }
  }
  return "";
}

// ---------------------------------------------------------------------------
// Read all 8 source files once (6 query files + git.ts + WorkflowCanvas.tsx)
// ---------------------------------------------------------------------------

const QUERIES_DIR = resolve(__dirname, "..");
const FEATURES_DIR = resolve(__dirname, "..", "..", "features");

const soulsSource = readFileSync(resolve(QUERIES_DIR, "souls.ts"), "utf-8");
const stepsSource = readFileSync(resolve(QUERIES_DIR, "steps.ts"), "utf-8");
const tasksSource = readFileSync(resolve(QUERIES_DIR, "tasks.ts"), "utf-8");
const workflowsSource = readFileSync(resolve(QUERIES_DIR, "workflows.ts"), "utf-8");
const runsSource = readFileSync(resolve(QUERIES_DIR, "runs.ts"), "utf-8");
const settingsSource = readFileSync(resolve(QUERIES_DIR, "settings.ts"), "utf-8");
const gitSource = readFileSync(resolve(QUERIES_DIR, "git.ts"), "utf-8");
const dashboardSource = readFileSync(resolve(QUERIES_DIR, "dashboard.ts"), "utf-8");
const workflowCanvasSource = readFileSync(
  resolve(FEATURES_DIR, "canvas", "WorkflowCanvas.tsx"),
  "utf-8",
);

// ---------------------------------------------------------------------------
// Reusable assertion helpers
// ---------------------------------------------------------------------------

/**
 * Asserts that a source file imports toast from sonner.
 * Accepts both named import styles:
 *   import { toast } from "sonner"
 *   import { toast } from 'sonner'
 */
function expectToastImport(source: string, fileName: string) {
  it(`imports toast from sonner`, () => {
    const hasImport =
      source.includes('import { toast } from "sonner"') ||
      source.includes("import { toast } from 'sonner'");
    expect(hasImport).toBe(true);
  });
}

/**
 * Asserts that a mutation function contains toast.success() with the expected message.
 */
function expectSuccessToast(
  source: string,
  hookName: string,
  expectedMessage: string
) {
  it(`${hookName} shows success toast: "${expectedMessage}"`, () => {
    const body = extractFunction(source, hookName);
    expect(body).not.toBe("");
    expect(body).toContain("toast.success");
    expect(body).toContain(expectedMessage);
  });
}

/**
 * Asserts that a mutation function contains toast.error() for failure handling.
 */
function expectErrorToast(source: string, hookName: string) {
  it(`${hookName} shows error toast on failure`, () => {
    const body = extractFunction(source, hookName);
    expect(body).not.toBe("");
    expect(body).toContain("toast.error");
  });
}

/**
 * Asserts that a mutation function has an onError callback.
 */
function expectOnErrorCallback(source: string, hookName: string) {
  it(`${hookName} has an onError callback`, () => {
    const body = extractFunction(source, hookName);
    expect(body).not.toBe("");
    expect(body).toContain("onError");
  });
}

// ---------------------------------------------------------------------------
// 1. souls.ts — 3 mutations
// ---------------------------------------------------------------------------

describe("souls.ts toast notifications (RUN-240)", () => {
  expectToastImport(soulsSource, "souls.ts");

  expectSuccessToast(soulsSource, "useCreateSoul", "Soul created");
  expectErrorToast(soulsSource, "useCreateSoul");
  expectOnErrorCallback(soulsSource, "useCreateSoul");

  expectSuccessToast(soulsSource, "useUpdateSoul", "Soul updated");
  expectErrorToast(soulsSource, "useUpdateSoul");
  expectOnErrorCallback(soulsSource, "useUpdateSoul");

  expectSuccessToast(soulsSource, "useDeleteSoul", "Soul deleted");
  expectErrorToast(soulsSource, "useDeleteSoul");
  expectOnErrorCallback(soulsSource, "useDeleteSoul");
});

// ---------------------------------------------------------------------------
// 2. steps.ts — 3 mutations
// ---------------------------------------------------------------------------

describe("steps.ts toast notifications (RUN-240)", () => {
  expectToastImport(stepsSource, "steps.ts");

  expectSuccessToast(stepsSource, "useCreateStep", "Step created");
  expectErrorToast(stepsSource, "useCreateStep");
  expectOnErrorCallback(stepsSource, "useCreateStep");

  expectSuccessToast(stepsSource, "useUpdateStep", "Step updated");
  expectErrorToast(stepsSource, "useUpdateStep");
  expectOnErrorCallback(stepsSource, "useUpdateStep");

  expectSuccessToast(stepsSource, "useDeleteStep", "Step deleted");
  expectErrorToast(stepsSource, "useDeleteStep");
  expectOnErrorCallback(stepsSource, "useDeleteStep");
});

// ---------------------------------------------------------------------------
// 3. tasks.ts — 3 mutations
// ---------------------------------------------------------------------------

describe("tasks.ts toast notifications (RUN-240)", () => {
  expectToastImport(tasksSource, "tasks.ts");

  expectSuccessToast(tasksSource, "useCreateTask", "Task created");
  expectErrorToast(tasksSource, "useCreateTask");
  expectOnErrorCallback(tasksSource, "useCreateTask");

  expectSuccessToast(tasksSource, "useUpdateTask", "Task updated");
  expectErrorToast(tasksSource, "useUpdateTask");
  expectOnErrorCallback(tasksSource, "useUpdateTask");

  expectSuccessToast(tasksSource, "useDeleteTask", "Task deleted");
  expectErrorToast(tasksSource, "useDeleteTask");
  expectOnErrorCallback(tasksSource, "useDeleteTask");
});

// ---------------------------------------------------------------------------
// 4. workflows.ts — 3 mutations
// ---------------------------------------------------------------------------

describe("workflows.ts toast notifications (RUN-240)", () => {
  expectToastImport(workflowsSource, "workflows.ts");

  expectSuccessToast(workflowsSource, "useCreateWorkflow", "Workflow created");
  expectErrorToast(workflowsSource, "useCreateWorkflow");
  expectOnErrorCallback(workflowsSource, "useCreateWorkflow");

  expectSuccessToast(workflowsSource, "useUpdateWorkflow", "Workflow updated");
  expectErrorToast(workflowsSource, "useUpdateWorkflow");
  expectOnErrorCallback(workflowsSource, "useUpdateWorkflow");

  expectSuccessToast(workflowsSource, "useDeleteWorkflow", "Workflow deleted");
  expectErrorToast(workflowsSource, "useDeleteWorkflow");
  expectOnErrorCallback(workflowsSource, "useDeleteWorkflow");
});

// ---------------------------------------------------------------------------
// 5. runs.ts — 3 mutations
// ---------------------------------------------------------------------------

describe("runs.ts toast notifications (RUN-240)", () => {
  expectToastImport(runsSource, "runs.ts");

  expectSuccessToast(runsSource, "useCreateRun", "Run started");
  expectErrorToast(runsSource, "useCreateRun");
  expectOnErrorCallback(runsSource, "useCreateRun");

  expectSuccessToast(runsSource, "useCancelRun", "Run cancelled");
  expectErrorToast(runsSource, "useCancelRun");
  expectOnErrorCallback(runsSource, "useCancelRun");

  expectSuccessToast(runsSource, "useDeleteRun", "Run deleted");
  expectErrorToast(runsSource, "useDeleteRun");
  expectOnErrorCallback(runsSource, "useDeleteRun");
});

// ---------------------------------------------------------------------------
// 6. settings.ts — 9 mutations
// ---------------------------------------------------------------------------

describe("settings.ts toast notifications (RUN-240)", () => {
  expectToastImport(settingsSource, "settings.ts");

  expectSuccessToast(settingsSource, "useCreateProvider", "Provider added");
  expectErrorToast(settingsSource, "useCreateProvider");
  expectOnErrorCallback(settingsSource, "useCreateProvider");

  expectSuccessToast(settingsSource, "useUpdateProvider", "Provider updated");
  expectErrorToast(settingsSource, "useUpdateProvider");
  expectOnErrorCallback(settingsSource, "useUpdateProvider");

  expectSuccessToast(settingsSource, "useDeleteProvider", "Provider deleted");
  expectErrorToast(settingsSource, "useDeleteProvider");
  expectOnErrorCallback(settingsSource, "useDeleteProvider");

  expectSuccessToast(settingsSource, "useTestProviderConnection", "Connection successful");
  expectErrorToast(settingsSource, "useTestProviderConnection");
  expectOnErrorCallback(settingsSource, "useTestProviderConnection");

  expectSuccessToast(settingsSource, "useUpdateModelDefault", "Model default updated");
  expectErrorToast(settingsSource, "useUpdateModelDefault");
  expectOnErrorCallback(settingsSource, "useUpdateModelDefault");

  expectSuccessToast(settingsSource, "useCreateBudget", "Budget created");
  expectErrorToast(settingsSource, "useCreateBudget");
  expectOnErrorCallback(settingsSource, "useCreateBudget");

  expectSuccessToast(settingsSource, "useUpdateBudget", "Budget updated");
  expectErrorToast(settingsSource, "useUpdateBudget");
  expectOnErrorCallback(settingsSource, "useUpdateBudget");

  expectSuccessToast(settingsSource, "useDeleteBudget", "Budget deleted");
  expectErrorToast(settingsSource, "useDeleteBudget");
  expectOnErrorCallback(settingsSource, "useDeleteBudget");

  expectSuccessToast(settingsSource, "useUpdateAppSettings", "Settings saved");
  expectErrorToast(settingsSource, "useUpdateAppSettings");
  expectOnErrorCallback(settingsSource, "useUpdateAppSettings");
});

// ---------------------------------------------------------------------------
// 7. git.ts — 1 mutation (useCommit)
// ---------------------------------------------------------------------------

describe("git.ts toast notifications (RUN-240)", () => {
  expectToastImport(gitSource, "git.ts");

  expectSuccessToast(gitSource, "useCommit", "Changes committed");
  expectErrorToast(gitSource, "useCommit");
  expectOnErrorCallback(gitSource, "useCommit");
});

// ---------------------------------------------------------------------------
// 8. WorkflowCanvas.tsx — onSave handler (AC3: canvas save toast)
// ---------------------------------------------------------------------------

describe("WorkflowCanvas.tsx canvas save toast (RUN-240 AC3)", () => {
  it("imports toast from sonner", () => {
    const hasImport =
      workflowCanvasSource.includes('import { toast } from "sonner"') ||
      workflowCanvasSource.includes("import { toast } from 'sonner'") ||
      // Also accept multi-import style: import { ..., toast, ... }
      /import\s*\{[^}]*toast[^}]*\}\s*from\s*["']sonner["']/.test(workflowCanvasSource);
    expect(hasImport).toBe(true);
  });

  it("onSave handler shows toast.success('Workflow saved') on success", () => {
    // The onSave handler is defined as `const onSave = async () => {`
    // Extract from that point using brace-depth tracking
    const startMarker = "const onSave = async";
    const startIdx = workflowCanvasSource.indexOf(startMarker);
    expect(startIdx).toBeGreaterThan(-1);

    let depth = 0;
    let bodyStart = -1;
    let onSaveBody = "";
    for (let i = startIdx; i < workflowCanvasSource.length; i++) {
      if (workflowCanvasSource[i] === "{") {
        if (bodyStart === -1) bodyStart = i;
        depth++;
      } else if (workflowCanvasSource[i] === "}") {
        depth--;
        if (depth === 0) {
          onSaveBody = workflowCanvasSource.slice(bodyStart, i + 1);
          break;
        }
      }
    }

    expect(onSaveBody).not.toBe("");
    expect(onSaveBody).toContain('toast.success("Workflow saved")');
  });

  it("onSave handler shows toast.error on failure", () => {
    const startMarker = "const onSave = async";
    const startIdx = workflowCanvasSource.indexOf(startMarker);
    expect(startIdx).toBeGreaterThan(-1);

    let depth = 0;
    let bodyStart = -1;
    let onSaveBody = "";
    for (let i = startIdx; i < workflowCanvasSource.length; i++) {
      if (workflowCanvasSource[i] === "{") {
        if (bodyStart === -1) bodyStart = i;
        depth++;
      } else if (workflowCanvasSource[i] === "}") {
        depth--;
        if (depth === 0) {
          onSaveBody = workflowCanvasSource.slice(bodyStart, i + 1);
          break;
        }
      }
    }

    expect(onSaveBody).not.toBe("");
    expect(onSaveBody).toContain("toast.error");
  });
});

// ---------------------------------------------------------------------------
// 9. Cross-cutting: Only mutations have toasts, not queries
// ---------------------------------------------------------------------------

describe("Only mutations have toasts, not queries (RUN-240)", () => {
  const queryFunctions = [
    { source: soulsSource, names: ["useSouls", "useSoul"] },
    { source: stepsSource, names: ["useSteps", "useStep"] },
    { source: tasksSource, names: ["useTasks", "useTask"] },
    { source: workflowsSource, names: ["useWorkflows", "useWorkflow"] },
    { source: runsSource, names: ["useRuns", "useRun", "useRunNodes", "useRunLogs"] },
    {
      source: settingsSource,
      names: ["useProviders", "useProvider", "useModelDefaults", "useBudgets", "useAppSettings"],
    },
    { source: gitSource, names: ["useGitStatus", "useGitLog", "useGitDiff"] },
    { source: dashboardSource, names: ["useDashboardSummary", "useRecentRuns"] },
  ];

  for (const { source, names } of queryFunctions) {
    for (const name of names) {
      it(`${name} (query) does NOT contain toast calls`, () => {
        const body = extractFunction(source, name);
        // Query functions should exist but should NOT have toast calls
        if (body) {
          expect(body).not.toContain("toast.success");
          expect(body).not.toContain("toast.error");
        }
      });
    }
  }
});

// ---------------------------------------------------------------------------
// 10. Error toasts include the error message via description
// ---------------------------------------------------------------------------

describe("Error toasts include error.message in description (RUN-240)", () => {
  const allMutations: Array<{ source: string; hookName: string; file: string }> = [
    // souls.ts
    { source: soulsSource, hookName: "useCreateSoul", file: "souls.ts" },
    { source: soulsSource, hookName: "useUpdateSoul", file: "souls.ts" },
    { source: soulsSource, hookName: "useDeleteSoul", file: "souls.ts" },
    // steps.ts
    { source: stepsSource, hookName: "useCreateStep", file: "steps.ts" },
    { source: stepsSource, hookName: "useUpdateStep", file: "steps.ts" },
    { source: stepsSource, hookName: "useDeleteStep", file: "steps.ts" },
    // tasks.ts
    { source: tasksSource, hookName: "useCreateTask", file: "tasks.ts" },
    { source: tasksSource, hookName: "useUpdateTask", file: "tasks.ts" },
    { source: tasksSource, hookName: "useDeleteTask", file: "tasks.ts" },
    // workflows.ts
    { source: workflowsSource, hookName: "useCreateWorkflow", file: "workflows.ts" },
    { source: workflowsSource, hookName: "useUpdateWorkflow", file: "workflows.ts" },
    { source: workflowsSource, hookName: "useDeleteWorkflow", file: "workflows.ts" },
    // runs.ts
    { source: runsSource, hookName: "useCreateRun", file: "runs.ts" },
    { source: runsSource, hookName: "useCancelRun", file: "runs.ts" },
    { source: runsSource, hookName: "useDeleteRun", file: "runs.ts" },
    // git.ts
    { source: gitSource, hookName: "useCommit", file: "git.ts" },
    // settings.ts
    { source: settingsSource, hookName: "useCreateProvider", file: "settings.ts" },
    { source: settingsSource, hookName: "useUpdateProvider", file: "settings.ts" },
    { source: settingsSource, hookName: "useDeleteProvider", file: "settings.ts" },
    { source: settingsSource, hookName: "useTestProviderConnection", file: "settings.ts" },
    { source: settingsSource, hookName: "useUpdateModelDefault", file: "settings.ts" },
    { source: settingsSource, hookName: "useCreateBudget", file: "settings.ts" },
    { source: settingsSource, hookName: "useUpdateBudget", file: "settings.ts" },
    { source: settingsSource, hookName: "useDeleteBudget", file: "settings.ts" },
    { source: settingsSource, hookName: "useUpdateAppSettings", file: "settings.ts" },
  ];

  for (const { source, hookName, file } of allMutations) {
    it(`${file} > ${hookName} error toast passes error.message as description`, () => {
      const body = extractFunction(source, hookName);
      expect(body).not.toBe("");
      // The onError callback should pass error.message in the description field
      // Pattern: toast.error("...", { description: error.message })
      expect(body).toContain("error.message");
    });
  }
});
