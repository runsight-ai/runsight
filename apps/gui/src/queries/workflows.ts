import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { workflowsApi } from "../api/workflows";
import { queryKeys } from "./keys";
import type {
  WorkflowCreate,
  WorkflowListResponse,
  WorkflowResponse,
  WorkflowUpdate,
} from "@runsight/shared/zod";

export function useWorkflows() {
  return useQuery({
    queryKey: queryKeys.workflows.all,
    queryFn: workflowsApi.listWorkflows,
  });
}

export function useWorkflow(id: string) {
  return useQuery({
    queryKey: queryKeys.workflows.detail(id),
    queryFn: () => workflowsApi.getWorkflow(id),
    enabled: !!id,
  });
}

export function useCreateWorkflow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: WorkflowCreate) => workflowsApi.createWorkflow(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.workflows.all });
      toast.success("Workflow created");
    },
    onError: (error: Error) => {
      toast.error("Failed to create workflow", { description: error.message });
    },
  });
}

export function useUpdateWorkflow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: WorkflowUpdate }) =>
      workflowsApi.updateWorkflow(id, data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.workflows.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.workflows.detail(variables.id) });
      toast.success("Workflow updated");
    },
    onError: (error: Error) => {
      toast.error("Failed to update workflow", { description: error.message });
    },
  });
}

export function useSetWorkflowEnabled() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      workflowsApi.setWorkflowEnabled(id, enabled),
    onMutate: async (variables) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.workflows.all });
      await queryClient.cancelQueries({
        queryKey: queryKeys.workflows.detail(variables.id),
      });

      const previousList = queryClient.getQueryData<WorkflowListResponse>(
        queryKeys.workflows.all,
      );
      const previousDetail = queryClient.getQueryData<WorkflowResponse>(
        queryKeys.workflows.detail(variables.id),
      );

      queryClient.setQueryData<WorkflowListResponse>(
        queryKeys.workflows.all,
        (current) =>
          current
            ? {
                ...current,
                items: current.items.map((workflow) =>
                  workflow.id === variables.id
                    ? { ...workflow, enabled: variables.enabled }
                    : workflow,
                ),
              }
            : current,
      );

      queryClient.setQueryData<WorkflowResponse>(
        queryKeys.workflows.detail(variables.id),
        (current) =>
          current
            ? {
                ...current,
                enabled: variables.enabled,
              }
            : current,
      );

      return { previousList, previousDetail };
    },
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.workflows.detail(data.id), data);
      queryClient.setQueryData<WorkflowListResponse>(
        queryKeys.workflows.all,
        (current) =>
          current
            ? {
                ...current,
                items: current.items.map((workflow) =>
                  workflow.id === data.id ? data : workflow,
                ),
              }
            : current,
      );
    },
    onError: (error: Error, variables, context) => {
      if (context?.previousList) {
        queryClient.setQueryData(queryKeys.workflows.all, context.previousList);
      }
      if (context?.previousDetail) {
        queryClient.setQueryData(
          queryKeys.workflows.detail(variables.id),
          context.previousDetail,
        );
      }
      toast.error("Failed to update workflow", { description: error.message });
    },
  });
}

export function useWorkflowRegressions(workflowId: string) {
  return useQuery({
    queryKey: queryKeys.workflows.regressions(workflowId),
    queryFn: () => workflowsApi.getWorkflowRegressions(workflowId),
    enabled: !!workflowId,
  });
}

export function useDeleteWorkflow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => workflowsApi.deleteWorkflow(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.workflows.all });
      toast.success("Workflow deleted");
    },
    onError: (error: Error) => {
      toast.error("Failed to delete workflow", { description: error.message });
    },
  });
}
