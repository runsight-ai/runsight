import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { settingsApi } from "../api/settings";
import { queryKeys } from "./keys";

export function useProviders(params?: Record<string, string>) {
  return useQuery({
    queryKey: [...queryKeys.settings.providers, params],
    queryFn: () => settingsApi.listProviders(params),
  });
}

export function useProvider(id: string) {
  return useQuery({
    queryKey: queryKeys.settings.provider(id),
    queryFn: () => settingsApi.getProvider(id),
    enabled: !!id,
  });
}

export function useCreateProvider() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: settingsApi.createProvider,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.settings.providers });
    },
  });
}

export function useUpdateProvider() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Parameters<typeof settingsApi.updateProvider>[1] }) =>
      settingsApi.updateProvider(id, data),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.settings.providers });
      queryClient.invalidateQueries({ queryKey: queryKeys.settings.provider(id) });
    },
  });
}

export function useDeleteProvider() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: settingsApi.deleteProvider,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.settings.providers });
    },
  });
}

export function useTestProviderConnection() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: settingsApi.testProviderConnection,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.settings.providers });
    },
  });
}

export function useModelDefaults() {
  return useQuery({
    queryKey: queryKeys.settings.modelDefaults,
    queryFn: settingsApi.listModelDefaults,
  });
}

export function useUpdateModelDefault() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Parameters<typeof settingsApi.updateModelDefault>[1] }) =>
      settingsApi.updateModelDefault(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.settings.modelDefaults });
    },
  });
}

export function useBudgets() {
  return useQuery({
    queryKey: queryKeys.settings.budgets,
    queryFn: settingsApi.getBudgets,
  });
}

export function useCreateBudget() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: settingsApi.createBudget,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.settings.budgets });
    },
  });
}

export function useUpdateBudget() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Parameters<typeof settingsApi.updateBudget>[1] }) =>
      settingsApi.updateBudget(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.settings.budgets });
    },
  });
}

export function useDeleteBudget() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: settingsApi.deleteBudget,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.settings.budgets });
    },
  });
}

export function useAppSettings() {
  return useQuery({
    queryKey: queryKeys.settings.appSettings,
    queryFn: settingsApi.getAppSettings,
  });
}

export function useUpdateAppSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: settingsApi.updateAppSettings,
    onMutate: (newSettings) => {
      const prev = queryClient.getQueryData(queryKeys.settings.appSettings);
      queryClient.setQueryData(queryKeys.settings.appSettings, (old: Record<string, unknown> | undefined) => ({
        ...old,
        ...newSettings,
      }));
      return { prev };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.settings.appSettings });
    },
    onError: (_err, _vars, context) => {
      if (context?.prev) {
        queryClient.setQueryData(queryKeys.settings.appSettings, context.prev);
      }
    },
  });
}
