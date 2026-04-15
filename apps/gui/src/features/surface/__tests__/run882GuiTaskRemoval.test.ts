/**
 * RED-TEAM tests for RUN-882: GUI — RunButton inputs, delete TaskNode, update shared schemas.
 *
 * Acceptance Criteria:
 *   AC1: RunButton no longer sends taskData
 *   AC2: runWorkflow.ts passes inputs to createRun
 *   AC3: TaskNode component deleted
 *   AC4: nodeTypes map has no task entry
 *   AC5: LeftSidebarTab has no "tasks" option
 *   AC6: Shared Zod schemas have no Task types
 *   AC7: GUI builds without errors (api.ts has no /api/tasks paths)
 *
 * All tests are expected to FAIL because:
 *   - RunButton.tsx still defines `const taskData = { instruction: "Execute workflow" }`
 *   - RunButton.tsx still passes `task_data: taskData` in both mutate calls
 *   - runWorkflow.ts still accepts `taskData` option and forwards it as `task_data`
 *   - TaskNode.tsx still exists at features/surface/nodes/TaskNode.tsx
 *   - nodes/index.ts still imports TaskNode and maps it as `task:` in nodeTypes
 *   - canvas.ts LeftSidebarTab still includes "tasks"
 *   - zod.ts still exports TaskCreateSchema, TaskResponseSchema, TaskListResponseSchema, TaskUpdateSchema
 *   - api.ts still defines /api/tasks and /api/tasks/{id} paths
 */

import { describe, it, expect } from "vitest";
import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SRC_DIR = resolve(__dirname, "../../..");
const SHARED_SRC_DIR = resolve(
  __dirname,
  "../../../../../../packages/shared/src",
);

function readSource(relativePath: string): string {
  return readFileSync(resolve(SRC_DIR, relativePath), "utf-8");
}

function readShared(relativePath: string): string {
  return readFileSync(resolve(SHARED_SRC_DIR, relativePath), "utf-8");
}

function fileExists(relativePath: string): boolean {
  return existsSync(resolve(SRC_DIR, relativePath));
}

// ===========================================================================
// AC1: RunButton no longer sends taskData
// ===========================================================================

describe("AC1: RunButton no longer sends taskData (RUN-882)", () => {
  const RUN_BUTTON_PATH = "features/surface/RunButton.tsx";

  it("RunButton.tsx does NOT define a taskData variable", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // Should NOT have `const taskData = ...` or `taskData` variable declaration
    expect(source).not.toMatch(/\bconst taskData\b/);
  });

  it("RunButton.tsx does NOT pass task_data in simulation mutate call", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // Should NOT contain task_data anywhere in the mutation payloads
    expect(source).not.toMatch(/task_data\s*:/);
  });

  it("RunButton.tsx does NOT pass task_data in manual mutate call", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // Neither simulation nor manual branch should forward task_data
    // This is a stricter check that task_data is absent entirely
    expect(source).not.toMatch(/task_data/);
  });

  it("RunButton.tsx passes inputs (not taskData) to createRun simulation branch", () => {
    const source = readSource(RUN_BUTTON_PATH);
    // The simulation mutate call should include `inputs:` instead
    expect(source).toMatch(/inputs\s*:/);
  });
});

// ===========================================================================
// AC2: runWorkflow.ts passes inputs to createRun
// ===========================================================================

describe("AC2: runWorkflow.ts uses inputs instead of task_data (RUN-882)", () => {
  const RUN_WORKFLOW_PATH = "features/surface/runWorkflow.ts";

  it("runWorkflow.ts does NOT define taskData option in RunWorkflowOptions", () => {
    const source = readSource(RUN_WORKFLOW_PATH);
    // The interface should no longer have `taskData?:` field
    expect(source).not.toMatch(/\btaskData\??\s*:/);
  });

  it("runWorkflow.ts does NOT forward task_data to createRun", () => {
    const source = readSource(RUN_WORKFLOW_PATH);
    // createRun call should not include task_data
    expect(source).not.toMatch(/task_data\s*:/);
  });

  it("runWorkflow.ts does NOT destructure taskData from options", () => {
    const source = readSource(RUN_WORKFLOW_PATH);
    // The destructuring of options should not include taskData
    expect(source).not.toMatch(/\btaskData\b/);
  });

  it("runWorkflow.ts passes inputs to createRun call", () => {
    const source = readSource(RUN_WORKFLOW_PATH);
    // The createRun payload should include `inputs:`
    expect(source).toMatch(/inputs\s*:/);
  });

  it("RunWorkflowOptions interface defines inputs not taskData", () => {
    const source = readSource(RUN_WORKFLOW_PATH);
    // Interface should declare inputs option
    expect(source).toMatch(/inputs\??\s*:/);
  });
});

// ===========================================================================
// AC3: TaskNode component deleted
// ===========================================================================

describe("AC3: TaskNode component deleted (RUN-882)", () => {
  const TASK_NODE_PATH = "features/surface/nodes/TaskNode.tsx";

  it("TaskNode.tsx file does NOT exist", () => {
    expect(
      fileExists(TASK_NODE_PATH),
      "Expected features/surface/nodes/TaskNode.tsx to NOT exist (should be deleted)",
    ).toBe(false);
  });
});

// ===========================================================================
// AC4: nodeTypes map has no task entry
// ===========================================================================

describe("AC4: nodeTypes map has no task entry (RUN-882)", () => {
  const NODES_INDEX_PATH = "features/surface/nodes/index.ts";

  it("nodes/index.ts does NOT import TaskNode", () => {
    const source = readSource(NODES_INDEX_PATH);
    expect(source).not.toMatch(/import.*TaskNode/);
  });

  it("nodes/index.ts does NOT export TaskNode", () => {
    const source = readSource(NODES_INDEX_PATH);
    expect(source).not.toMatch(/export.*\bTaskNode\b/);
  });

  it("nodes/index.ts nodeTypes object does NOT have a task: entry", () => {
    const source = readSource(NODES_INDEX_PATH);
    // Should not have `task: TaskNode` or `task:` key in nodeTypes
    expect(source).not.toMatch(/\btask\s*:/);
  });

  it("nodes/index.ts does NOT reference TaskNode anywhere", () => {
    const source = readSource(NODES_INDEX_PATH);
    expect(source).not.toMatch(/\bTaskNode\b/);
  });
});

// ===========================================================================
// AC5: LeftSidebarTab has no "tasks" option
// ===========================================================================

describe("AC5: LeftSidebarTab does not include tasks (RUN-882)", () => {
  const CANVAS_SCHEMA_PATH = "types/schemas/canvas.ts";

  it("canvas.ts LeftSidebarTab type does NOT include 'tasks'", () => {
    const source = readSource(CANVAS_SCHEMA_PATH);
    // LeftSidebarTab = "souls" | "tasks" | "tools"
    // After cleanup: "souls" | "tools" — no "tasks"
    expect(source).not.toMatch(/LeftSidebarTab.*tasks|"tasks".*LeftSidebarTab/);
  });

  it("canvas.ts LeftSidebarTab line does NOT contain the string 'tasks'", () => {
    const source = readSource(CANVAS_SCHEMA_PATH);
    // Extract the LeftSidebarTab declaration line and check it
    const match = source.match(/export type LeftSidebarTab\s*=\s*[^;]+;/);
    expect(match, "Expected to find LeftSidebarTab type declaration").toBeTruthy();
    const declaration = match![0];
    expect(declaration).not.toMatch(/"tasks"/);
  });
});

// ===========================================================================
// AC6: Shared Zod schemas have no Task types
// ===========================================================================

describe("AC6: zod.ts has no Task schemas (RUN-882)", () => {
  it("zod.ts does NOT export TaskCreateSchema", () => {
    const source = readShared("zod.ts");
    expect(source).not.toMatch(/\bTaskCreateSchema\b/);
  });

  it("zod.ts does NOT export TaskResponseSchema", () => {
    const source = readShared("zod.ts");
    expect(source).not.toMatch(/\bTaskResponseSchema\b/);
  });

  it("zod.ts does NOT export TaskListResponseSchema", () => {
    const source = readShared("zod.ts");
    expect(source).not.toMatch(/\bTaskListResponseSchema\b/);
  });

  it("zod.ts does NOT export TaskUpdateSchema", () => {
    const source = readShared("zod.ts");
    expect(source).not.toMatch(/\bTaskUpdateSchema\b/);
  });

  it("zod.ts does NOT export TaskCreate type", () => {
    const source = readShared("zod.ts");
    expect(source).not.toMatch(/\bexport type TaskCreate\b/);
  });

  it("zod.ts does NOT export TaskResponse type", () => {
    const source = readShared("zod.ts");
    expect(source).not.toMatch(/\bexport type TaskResponse\b/);
  });

  it("zod.ts does NOT export TaskListResponse type", () => {
    const source = readShared("zod.ts");
    expect(source).not.toMatch(/\bexport type TaskListResponse\b/);
  });

  it("zod.ts does NOT export TaskUpdate type", () => {
    const source = readShared("zod.ts");
    expect(source).not.toMatch(/\bexport type TaskUpdate\b/);
  });

  it("RunCreateSchema uses inputs field not task_data", () => {
    const source = readShared("zod.ts");
    // After RUN-882, RunCreateSchema should have `inputs` instead of `task_data`
    const match = source.match(
      /export const RunCreateSchema\s*=\s*z\.object\(\{[^}]+\}\)/s,
    );
    expect(match, "Expected to find RunCreateSchema definition").toBeTruthy();
    const definition = match![0];
    expect(definition).not.toMatch(/task_data/);
    expect(definition).toMatch(/inputs/);
  });
});

// ===========================================================================
// AC7: api.ts has no /api/tasks paths
// ===========================================================================

describe("AC7: api.ts has no /api/tasks paths (RUN-882)", () => {
  it("api.ts does NOT define /api/tasks path", () => {
    const source = readShared("api.ts");
    expect(source).not.toMatch(/["'`]\/api\/tasks["'`]/);
  });

  it("api.ts does NOT define /api/tasks/{id} path", () => {
    const source = readShared("api.ts");
    expect(source).not.toMatch(/["'`]\/api\/tasks\/\{id\}["'`]/);
  });

  it("api.ts does NOT reference list_tasks operation", () => {
    const source = readShared("api.ts");
    expect(source).not.toMatch(/list_tasks/);
  });

  it("api.ts does NOT reference create_task operation", () => {
    const source = readShared("api.ts");
    expect(source).not.toMatch(/create_task/);
  });

  it("api.ts does NOT reference get_task operation", () => {
    const source = readShared("api.ts");
    expect(source).not.toMatch(/get_task/);
  });

  it("api.ts does NOT reference update_task operation", () => {
    const source = readShared("api.ts");
    expect(source).not.toMatch(/update_task/);
  });

  it("api.ts does NOT reference delete_task operation", () => {
    const source = readShared("api.ts");
    expect(source).not.toMatch(/delete_task/);
  });
});
