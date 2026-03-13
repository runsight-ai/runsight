import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { soulsApi } from "../api/souls";
import { queryKeys } from "./keys";
import { SoulCreate, SoulUpdate } from "../types/schemas/souls";

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
    },
  });
}

export function useDeleteSoul() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => soulsApi.deleteSoul(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.souls.all });
    },
  });
}
