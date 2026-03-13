import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { stepsApi } from "../api/steps";
import { queryKeys } from "./keys";
import type { StepCreate, StepUpdate } from "../types/schemas/steps";

export function useSteps(params?: Record<string, string>) {
  return useQuery({
    queryKey: [...queryKeys.steps.all, params],
    queryFn: () => stepsApi.listSteps(params),
  });
}

export function useStep(id: string) {
  return useQuery({
    queryKey: queryKeys.steps.detail(id),
    queryFn: () => stepsApi.getStep(id),
    enabled: !!id,
  });
}

export function useCreateStep() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: StepCreate) => stepsApi.createStep(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.steps.all });
    },
  });
}

export function useUpdateStep() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: StepUpdate }) =>
      stepsApi.updateStep(id, data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.steps.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.steps.detail(variables.id) });
    },
  });
}

export function useDeleteStep() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => stepsApi.deleteStep(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.steps.all });
    },
  });
}
