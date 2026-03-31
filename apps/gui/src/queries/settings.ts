import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
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

export function useModelProviders() {
  return useQuery({
    queryKey: queryKeys.models.providers,
    queryFn: () => settingsApi.listModelProviders(),
  });
}

export function useModelsForProvider(provider: string | null) {
  return useQuery({
    queryKey: queryKeys.models.byProvider(provider),
    queryFn: () => settingsApi.listModelsForProvider(provider!),
    enabled: !!provider,
  });
}

export function useCreateProvider() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: settingsApi.createProvider,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.settings.providers });
      toast.success("Provider added");
    },
    onError: (error: Error) => {
      toast.error("Failed to add provider", { description: error.message });
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
      toast.success("Provider updated");
    },
    onError: (error: Error) => {
      toast.error("Failed to update provider", { description: error.message });
    },
  });
}

export function useDeleteProvider() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: settingsApi.deleteProvider,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.settings.providers });
      toast.success("Provider deleted");
    },
    onError: (error: Error) => {
      toast.error("Failed to delete provider", { description: error.message });
    },
  });
}

export function useTestProviderConnection() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: settingsApi.testProviderConnection,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.settings.providers });
      toast.success("Connection successful");
    },
    onError: (error: Error) => {
      toast.error("Failed to test connection", { description: error.message });
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
      toast.success("Model default updated");
    },
    onError: (error: Error) => {
      toast.error("Failed to update model default", { description: error.message });
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
      toast.success("Budget created");
    },
    onError: (error: Error) => {
      toast.error("Failed to create budget", { description: error.message });
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
      toast.success("Budget updated");
    },
    onError: (error: Error) => {
      toast.error("Failed to update budget", { description: error.message });
    },
  });
}

export function useDeleteBudget() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: settingsApi.deleteBudget,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.settings.budgets });
      toast.success("Budget deleted");
    },
    onError: (error: Error) => {
      toast.error("Failed to delete budget", { description: error.message });
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
      toast.success("Settings saved");
    },
    onError: (error: Error, _vars, context) => {
      if (context?.prev) {
        queryClient.setQueryData(queryKeys.settings.appSettings, context.prev);
      }
      toast.error("Failed to save settings", { description: error.message });
    },
  });
}
