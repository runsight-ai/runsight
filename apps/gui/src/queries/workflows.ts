import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { workflowsApi } from "../api/workflows";
import { api } from "../api/client";
import { queryKeys } from "./keys";
import { WorkflowCreate, WorkflowUpdate } from "../types/schemas/workflows";

// Git types for commit functionality
export type FileChangeType = "M" | "A" | "D";

export interface FileChange {
  type: FileChangeType;
  path: string;
}

export interface GitStatusResponse {
  hasUncommitted: boolean;
  changedFiles: FileChange[];
  branch: string;
}

export interface CommitRequest {
  message: string;
  files?: string[];
}

export interface CommitResponse {
  success: boolean;
  commitHash: string;
  message: string;
}

// Mock git API for development (will be replaced with real API)
export const gitApi = {
  getStatus: async (workflowId: string): Promise<GitStatusResponse> => {
    const response = await api.get<{ is_dirty: boolean; changed_files: { path: string; status: string }[] }>(`/git/status?workflow_id=${workflowId}`);
    return {
      hasUncommitted: response.is_dirty,
      changedFiles: response.changed_files.map((f) => ({
        type: f.status as FileChangeType,
        path: f.path,
      })),
      branch: "main",
    };
  },

  commit: async (
    workflowId: string,
    request: CommitRequest
  ): Promise<CommitResponse> => {
    const response = await api.post<{ success: boolean; commit_hash: string; message: string }>(`/git/commit`, {
      workflow_id: workflowId,
      message: request.message,
      files: request.files,
    });
    return {
      success: response.success,
      commitHash: response.commit_hash,
      message: response.message,
    };
  },

  suggestCommitMessage: async (
    workflowId: string,
    changedFiles: FileChange[]
  ): Promise<string> => {
    const response = await api.post<{ suggestion: string }>(`/git/suggest-message`, {
      workflow_id: workflowId,
      changed_files: changedFiles,
    });
    return response.suggestion;
  },
};

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
    },
  });
}

export function useDeleteWorkflow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => workflowsApi.deleteWorkflow(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.workflows.all });
    },
  });
}

// Git/Commit hooks
export function useGitStatus(workflowId: string) {
  return useQuery({
    queryKey: [...queryKeys.workflows.detail(workflowId), "git", "status"],
    queryFn: () => gitApi.getStatus(workflowId),
    enabled: !!workflowId,
    // Refresh every 30 seconds to detect external changes
    refetchInterval: 30000,
  });
}

export function useCommitWorkflow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, message }: { id: string; message: string }) =>
      gitApi.commit(id, { message }),
    onSuccess: (_data, variables) => {
      // Invalidate git status to refresh the uncommitted badge
      queryClient.invalidateQueries({
        queryKey: [...queryKeys.workflows.detail(variables.id), "git"],
      });
    },
  });
}

export function useAiSuggestCommit() {
  return useMutation({
    mutationFn: ({
      id,
      changedFiles,
    }: {
      id: string;
      changedFiles: FileChange[];
    }) => gitApi.suggestCommitMessage(id, changedFiles),
  });
}
