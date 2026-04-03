import * as workflowQueries from "@/queries/workflows";

type WorkflowResult = ReturnType<typeof workflowQueries.useWorkflow>;
type WorkflowRegressionsResult = ReturnType<typeof workflowQueries.useWorkflowRegressions>;

function createMissingHookResult<T>(data?: T) {
  return { data } as {
    data: T | undefined;
  };
}

export function useWorkflow(id: string): WorkflowResult {
  const hook = "useWorkflow" in workflowQueries ? workflowQueries.useWorkflow : undefined;
  return hook ? hook(id) : createMissingHookResult() as WorkflowResult;
}

export function useWorkflowRegressions(workflowId: string): WorkflowRegressionsResult {
  const hook =
    "useWorkflowRegressions" in workflowQueries
      ? workflowQueries.useWorkflowRegressions
      : undefined;
  return hook ? hook(workflowId) : createMissingHookResult() as WorkflowRegressionsResult;
}
