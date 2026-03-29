import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { soulsApi } from "../api/souls";
import { queryKeys } from "./keys";
import type { SoulCreate, SoulUpdate } from "@runsight/shared/zod";

export function useSouls() {
  return useQuery({
    queryKey: queryKeys.souls.all,
    queryFn: soulsApi.listSouls,
  });
}

export function useSoul(id: string) {
  return useQuery({
    queryKey: queryKeys.souls.detail(id),
    queryFn: () => soulsApi.getSoul(id),
    enabled: !!id,
  });
}

export function useCreateSoul() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: SoulCreate) => soulsApi.createSoul(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.souls.all });
      toast.success("Soul created");
    },
    onError: (error: Error) => {
      toast.error("Failed to create soul", { description: error.message });
    },
  });
}

export function useUpdateSoul() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: SoulUpdate }) =>
      soulsApi.updateSoul(id, data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.souls.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.souls.detail(variables.id) });
      toast.success("Soul updated");
    },
    onError: (error: Error) => {
      toast.error("Failed to update soul", { description: error.message });
    },
  });
}

export function useDeleteSoul() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => soulsApi.deleteSoul(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.souls.all });
      toast.success("Soul deleted");
    },
    onError: (error: Error) => {
      toast.error("Failed to delete soul", { description: error.message });
    },
  });
}
