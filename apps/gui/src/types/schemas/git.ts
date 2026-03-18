import { z } from "zod";

export const GitFileStatusSchema = z.object({
  path: z.string(),
  status: z.string(),
});

export type GitFileStatus = z.infer<typeof GitFileStatusSchema>;

export const GitStatusResponseSchema = z.object({
  branch: z.string(),
  uncommitted_files: z.array(GitFileStatusSchema),
  is_clean: z.boolean(),
});

export type GitStatusResponse = z.infer<typeof GitStatusResponseSchema>;

export const GitCommitResponseSchema = z.object({
  hash: z.string(),
  message: z.string(),
});

export type GitCommitResponse = z.infer<typeof GitCommitResponseSchema>;

export const GitLogEntrySchema = z.object({
  hash: z.string(),
  message: z.string(),
  date: z.string(),
  author: z.string(),
});

export type GitLogEntry = z.infer<typeof GitLogEntrySchema>;

export const GitDiffResponseSchema = z.object({
  diff: z.string(),
});

export type GitDiffResponse = z.infer<typeof GitDiffResponseSchema>;
