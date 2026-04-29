/**
 * Governance: retired task shared-contract boundary.
 *
 * Owner: shared contracts.
 * Boundary: generated shared schemas and OpenAPI types must not expose the
 * retired task API surface.
 * Exit criteria: remove once OpenAPI generation has a first-class denylist for
 * retired resources.
 */

import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import * as zodContracts from "../zod";
import { RunCreateSchema } from "../zod";

const SHARED_SRC_DIR = resolve(__dirname, "..");

describe("Governance: retired task shared-contract boundary", () => {
  it("does not export retired task schemas or types from zod contracts", () => {
    expect(zodContracts).not.toHaveProperty("TaskCreateSchema");
    expect(zodContracts).not.toHaveProperty("TaskResponseSchema");
    expect(zodContracts).not.toHaveProperty("TaskListResponseSchema");
    expect(zodContracts).not.toHaveProperty("TaskUpdateSchema");
  });

  it("keeps RunCreateSchema on inputs instead of task_data", () => {
    const shape = RunCreateSchema.shape as Record<string, unknown>;

    expect(shape).toHaveProperty("inputs");
    expect(shape).not.toHaveProperty("task_data");
  });

  it("does not expose retired /api/tasks paths in generated API types", () => {
    const apiSource = readFileSync(resolve(SHARED_SRC_DIR, "api.ts"), "utf-8");

    expect(apiSource).not.toContain("/api/tasks");
    expect(apiSource).not.toMatch(
      /(?:^|[^A-Za-z0-9])(?:list|create|get|update|delete)_tasks?(?:[^A-Za-z0-9]|$)/,
    );
    expect(apiSource).not.toContain("api_tasks");
  });
});
