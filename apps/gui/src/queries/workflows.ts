import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { workflowsApi } from "../api/workflows";
import { queryKeys } from "./keys";
import { WorkflowCreate, WorkflowUpdate } from "../types/schemas/workflows";

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
