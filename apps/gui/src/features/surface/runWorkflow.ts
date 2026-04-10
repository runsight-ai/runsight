import type { RunCreate } from "@runsight/shared/zod";

export interface RunWorkflowOptions {
  workflowId: string;
  save: () => Promise<void>;
  createRun: (data: RunCreate) => Promise<{ id: string; workflow_id: string }>;
  navigate?: (path: string) => void;
  onError?: (error: Error) => void;
  isRunning?: boolean;
  taskData?: Record<string, unknown>;
}

export interface RunWorkflowResult {
  runId: string;
}

export async function runWorkflow(
  options: RunWorkflowOptions,
): Promise<RunWorkflowResult | null> {
  const { workflowId, save, createRun, navigate, onError, isRunning, taskData } = options;

  if (isRunning) {
    return null;
  }

  try {
    await save();
  } catch (error) {
    if (onError && error instanceof Error) {
      onError(error);
    }
    throw error;
  }

  let result: { id: string; workflow_id: string };
  try {
    result = await createRun({
      workflow_id: workflowId,
      task_data: taskData ?? {},
    });
  } catch (error) {
    if (onError && error instanceof Error) {
      onError(error);
    }
    throw error;
  }

  if (navigate) {
    navigate(`/runs/${result.id}`);
  }

  return { runId: result.id };
}
