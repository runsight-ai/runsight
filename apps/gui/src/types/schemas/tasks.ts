import { z } from "zod";

export const TaskResponseSchema = z.object({
  id: z.string(),
  name: z.string(),
  type: z.string(),
  path: z.string(),
  description: z.string().nullable().optional(),
});
export type TaskResponse = z.infer<typeof TaskResponseSchema>;

export const TaskCreateSchema = z.object({
  id: z.string().nullable().optional(),
  name: z.string(),
  type: z.string().default("task"),
  description: z.string().nullable().optional(),
});
export type TaskCreate = z.infer<typeof TaskCreateSchema>;

export const TaskUpdateSchema = z.object({
  name: z.string().nullable().optional(),
  type: z.string().nullable().optional(),
  description: z.string().nullable().optional(),
});
export type TaskUpdate = z.infer<typeof TaskUpdateSchema>;

export const TaskListResponseSchema = z.object({
  items: z.array(TaskResponseSchema),
  total: z.number(),
});
export type TaskListResponse = z.infer<typeof TaskListResponseSchema>;
