import { describe, expect, it, vi } from "vitest";
import { ApiError } from "@/api/client";

const inputSchema = {
  query: {
    type: "string",
    required: true,
    default: null,
    description: "Search query",
    sensitive: false,
  },
};

async function loadPolicy() {
  return import("../runInputSchemaPolicy");
}

describe("RUN-900 run input schema policy", () => {
  it("uses backend input_schema for a clean saved workflow and skips simulation preparation", async () => {
    const { resolveRunInputSchemaDecision } = await loadPolicy();
    const prepareSimulation = vi.fn();

    const decision = await resolveRunInputSchemaDecision({
      workflow: {
        id: "wf_clean_900",
        input_schema: inputSchema,
      },
      isDirty: false,
      yamlContent: "workflow:\n  name: Clean Flow\n",
      prepareSimulation,
    });

    expect(prepareSimulation).not.toHaveBeenCalled();
    expect(decision).toEqual(
      expect.objectContaining({
        kind: "needs_inputs",
        input_schema: inputSchema,
      }),
    );
  });

  it("returns immediate when a clean saved workflow has no input_schema", async () => {
    const { resolveRunInputSchemaDecision } = await loadPolicy();
    const prepareSimulation = vi.fn();

    const decision = await resolveRunInputSchemaDecision({
      workflow: {
        id: "wf_clean_900_empty",
        input_schema: null,
      },
      isDirty: false,
      yamlContent: "workflow:\n  name: Clean Flow\n",
      prepareSimulation,
    });

    expect(prepareSimulation).not.toHaveBeenCalled();
    expect(decision).toEqual({ kind: "immediate" });
  });

  it("prepares a dirty workflow before deciding and preserves the snapshot identity when inputs are needed", async () => {
    const { resolveRunInputSchemaDecision } = await loadPolicy();
    const prepareSimulation = vi.fn().mockResolvedValue({
      branch: "sim/wf_dirty_900/20260419/abc12",
      commit_sha: "fedcba9876543210fedcba9876543210fedcba98",
      input_schema: inputSchema,
    });

    const decision = await resolveRunInputSchemaDecision({
      workflow: {
        id: "wf_dirty_900",
        input_schema: null,
      },
      isDirty: true,
      yamlContent: "workflow:\n  name: Dirty Flow\n",
      prepareSimulation,
    });

    expect(prepareSimulation).toHaveBeenCalledWith(
      "wf_dirty_900",
      "workflow:\n  name: Dirty Flow\n",
    );
    expect(decision).toEqual(
      expect.objectContaining({
        kind: "needs_inputs",
        branch: "sim/wf_dirty_900/20260419/abc12",
        commit_sha: "fedcba9876543210fedcba9876543210fedcba98",
        input_schema: inputSchema,
      }),
    );
  });

  it("returns immediate with the prepared snapshot identity when a dirty workflow has no inputs", async () => {
    const { resolveRunInputSchemaDecision } = await loadPolicy();
    const prepareSimulation = vi.fn().mockResolvedValue({
      branch: "sim/wf_dirty_900/20260419/def34",
      commit_sha: "0123456789abcdef0123456789abcdef01234567",
      input_schema: {},
    });

    const decision = await resolveRunInputSchemaDecision({
      workflow: {
        id: "wf_dirty_900_empty",
        input_schema: null,
      },
      isDirty: true,
      yamlContent: "workflow:\n  name: Dirty Flow\n",
      prepareSimulation,
    });

    expect(prepareSimulation).toHaveBeenCalledTimes(1);
    expect(decision).toEqual(
      expect.objectContaining({
        kind: "immediate",
        branch: "sim/wf_dirty_900/20260419/def34",
        commit_sha: "0123456789abcdef0123456789abcdef01234567",
      }),
    );
  });

  it("blocks dirty workflows when simulation preparation returns backend validation errors", async () => {
    const { resolveRunInputSchemaDecision } = await loadPolicy();
    const validationError = new ApiError(
      422,
      "WORKFLOW_INPUT_VALIDATION_ERROR",
      "Workflow input validation failed",
      {
        kind: "workflow_input_validation",
        workflow_id: "wf_dirty_900_invalid",
        fields: [
          {
            field: "query",
            code: "required",
            message: "Input 'query' is required.",
            input_path: ["inputs", "query"],
            expected_type: "string",
            actual_type: null,
          },
        ],
      },
    );
    const prepareSimulation = vi.fn().mockRejectedValue(validationError);

    const decision = await resolveRunInputSchemaDecision({
      workflow: {
        id: "wf_dirty_900_invalid",
        input_schema: null,
      },
      isDirty: true,
      yamlContent: "workflow:\n  name: Broken Flow\n",
      prepareSimulation,
    });

    expect(prepareSimulation).toHaveBeenCalledTimes(1);
    expect(decision).toEqual(
      expect.objectContaining({
        kind: "blocked",
        error: expect.objectContaining({
          status: 422,
          code: "WORKFLOW_INPUT_VALIDATION_ERROR",
          details: expect.objectContaining({
            kind: "workflow_input_validation",
            workflow_id: "wf_dirty_900_invalid",
          }),
        }),
      }),
    );
  });
});
