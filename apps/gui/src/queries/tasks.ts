import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { tasksApi } from "../api/tasks";
import { queryKeys } from "./keys";
import type { TaskCreate, TaskUpdate } from "../types/generated/zod";

export function useTasks(params?: Record<string, string>) {
  return useQuery({
    queryKey: [...queryKeys.tasks.all, params],
    queryFn: () => tasksApi.listTasks(params),
  });
}

export function useTask(id: string) {
  return useQuery({
    queryKey: queryKeys.tasks.detail(id),
    queryFn: () => tasksApi.getTask(id),
    enabled: !!id,
  });
}

export function useCreateTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: TaskCreate) => tasksApi.createTask(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all });
      toast.success("Task created");
    },
    onError: (error: Error) => {
      toast.error("Failed to create task", { description: error.message });
    },
  });
}

export function useUpdateTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: TaskUpdate }) =>
      tasksApi.updateTask(id, data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.detail(variables.id) });
      toast.success("Task updated");
    },
    onError: (error: Error) => {
      toast.error("Failed to update task", { description: error.message });
    },
  });
}

export function useDeleteTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => tasksApi.deleteTask(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all });
      toast.success("Task deleted");
    },
    onError: (error: Error) => {
      toast.error("Failed to delete task", { description: error.message });
    },
  });
}
