import { ApiError } from "@/api/client";
import type {
  WorkflowResponse,
  WorkflowSimulationResponse,
} from "@runsight/shared/zod";

type WorkflowInputSchema = NonNullable<WorkflowResponse["input_schema"]>;

type PrepareSimulation = (
  workflowId: string,
  yamlContent: string,
) => Promise<WorkflowSimulationResponse>;

type WorkflowForRunInputSchema = Pick<WorkflowResponse, "id" | "input_schema">;

export type RunInputSchemaDecision =
  | {
      kind: "immediate";
      branch?: string;
      commit_sha?: string;
    }
  | {
      kind: "needs_inputs";
      input_schema: WorkflowInputSchema;
      branch?: string;
      commit_sha?: string;
    }
  | {
      kind: "blocked";
      error: ApiError;
    };

export async function resolveRunInputSchemaDecision({
  workflow,
  isDirty,
  yamlContent,
  prepareSimulation,
}: {
  workflow: WorkflowForRunInputSchema;
  isDirty: boolean;
  yamlContent: string;
  prepareSimulation: PrepareSimulation;
}): Promise<RunInputSchemaDecision> {
  if (!isDirty) {
    return decisionForSchema(workflow.input_schema ?? undefined);
  }

  try {
    const simulation = await prepareSimulation(workflow.id, yamlContent);
    const snapshot = {
      branch: simulation.branch,
      commit_sha: simulation.commit_sha,
    };

    return decisionForSchema(simulation.input_schema, snapshot);
  } catch (error) {
    if (error instanceof ApiError) {
      return {
        kind: "blocked",
        error,
      };
    }

    throw error;
  }
}

function decisionForSchema(
  inputSchema: WorkflowInputSchema | null | undefined,
  snapshot?: { branch: string; commit_sha: string },
): RunInputSchemaDecision {
  if (!inputSchema || Object.keys(inputSchema).length === 0) {
    return {
      kind: "immediate",
      ...snapshot,
    };
  }

  return {
    kind: "needs_inputs",
    input_schema: inputSchema,
    ...snapshot,
  };
}
