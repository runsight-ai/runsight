import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { gitApi } from "../api/git";
import { queryKeys } from "./keys";
import { POLL_INTERVALS } from "../utils/constants";

export function useGitStatus(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: queryKeys.git.status,
    queryFn: () => gitApi.getStatus(),
    refetchInterval: POLL_INTERVALS.gitStatus,
    ...options,
  });
}

export function useGitLog(limit?: number) {
  return useQuery({
    queryKey: [...queryKeys.git.log, limit],
    queryFn: () => gitApi.getLog(limit),
  });
}

export function useGitDiff() {
  return useQuery({
    queryKey: queryKeys.git.diff,
    queryFn: () => gitApi.getDiff(),
  });
}

export function useCommit() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (message: string) => gitApi.commit(message),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.git.status });
      queryClient.invalidateQueries({ queryKey: queryKeys.git.log });
      toast.success("Changes committed");
    },
    onError: (error: Error) => {
      toast.error("Failed to commit changes", { description: error.message });
    },
  });
}
