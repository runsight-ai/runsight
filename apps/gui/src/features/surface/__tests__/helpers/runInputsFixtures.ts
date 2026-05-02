import type { RunResponse } from "@runsight/shared/zod";

export type SurfaceWorkflowInputSchemaItem = {
  type: "string" | "number" | "boolean" | "json" | "array";
  required?: boolean | null;
  default?: unknown;
  description?: string | null;
  sensitive?: boolean | null;
};

export type SurfaceWorkflowInputSnapshotEntry = {
  type: string;
  sensitive: boolean;
  source: string;
  value?: unknown;
};

export type SurfaceWorkflowRecordWithInputs = {
  id: string;
  name: string;
  input_schema: Record<string, SurfaceWorkflowInputSchemaItem> | null;
  commit_sha?: string | null;
};

export const DEFAULT_INPUTS_WORKFLOW = {
  id: "wf-inputs-defaults",
  name: "Nightly Search",
  input_schema: {
    query: {
      type: "string",
      required: true,
      default: "alpha",
      description: "Search term for the run.",
      sensitive: false,
    },
    config: {
      type: "json",
      required: false,
      default: { mode: "fast", retries: 2 },
      description: "Structured settings.",
      sensitive: false,
    },
    tags: {
      type: "array",
      required: false,
      default: ["one", "two"],
      description: "Ordered tags.",
      sensitive: false,
    },
  } satisfies Record<string, SurfaceWorkflowInputSchemaItem>,
} as const;

export const DEFAULTED_OPTIONAL_INPUTS_WORKFLOW = {
  ...DEFAULT_INPUTS_WORKFLOW,
  id: "wf-inputs-defaulted-optionals",
  input_schema: {
    query: DEFAULT_INPUTS_WORKFLOW.input_schema.query,
    limit: {
      type: "number",
      required: false,
      default: 25,
      description: "Optional result limit with a backend default.",
      sensitive: false,
    },
    config: {
      type: "json",
      required: false,
      default: { mode: "balanced", retries: 3 },
      description: "Optional structured settings with a backend default.",
      sensitive: false,
    },
    tags: {
      type: "array",
      required: false,
      default: ["alpha", "beta"],
      description: "Optional tags with a backend default.",
      sensitive: false,
    },
  } satisfies Record<string, SurfaceWorkflowInputSchemaItem>,
} as const;

export const REQUIRED_INPUTS_WORKFLOW = {
  ...DEFAULT_INPUTS_WORKFLOW,
  id: "wf-inputs-required",
  input_schema: {
    ...DEFAULT_INPUTS_WORKFLOW.input_schema,
    query: {
      ...DEFAULT_INPUTS_WORKFLOW.input_schema.query,
      default: null,
    },
  },
};

export const OPTIONAL_BLANK_INPUTS_WORKFLOW = {
  ...DEFAULT_INPUTS_WORKFLOW,
  id: "wf-inputs-optional-blanks",
  input_schema: {
    query: {
      type: "string",
      required: true,
      default: "alpha",
      description: "Search term for the run.",
      sensitive: false,
    },
    limit: {
      type: "number",
      required: false,
      default: null,
      description: "Optional result limit.",
      sensitive: false,
    },
    note: {
      type: "string",
      required: false,
      default: null,
      description: "Optional plain text note.",
      sensitive: false,
    },
    config: {
      type: "json",
      required: false,
      default: null,
      description: "Optional structured settings.",
      sensitive: false,
    },
    tags: {
      type: "array",
      required: false,
      default: null,
      description: "Optional tags.",
      sensitive: false,
    },
  } satisfies Record<string, SurfaceWorkflowInputSchemaItem>,
} as const;

export const RERUN_INPUTS_WORKFLOW = {
  ...DEFAULT_INPUTS_WORKFLOW,
  id: "wf-inputs-rerun",
};

export const RERUN_INITIAL_VALUES = {
  query: "prefilled rerun query",
  config: { mode: "slow", nested: { size: 2 } },
  tags: ["rerun", "ready"],
};

export const CURRENT_RERUN_WORKFLOW_ID = "wf_rerun_current";

export const CURRENT_RERUN_WORKFLOW: SurfaceWorkflowRecordWithInputs = {
  id: CURRENT_RERUN_WORKFLOW_ID,
  name: "Rerun Input Workflow",
  commit_sha: "abcdef1234567890",
  input_schema: {
    query: {
      type: "string",
      required: true,
      default: null,
      description: "Search term",
      sensitive: false,
    },
    api_token: {
      type: "string",
      required: true,
      default: null,
      description: "Secret token",
      sensitive: true,
    },
  },
};

export const SIMPLE_RERUN_WORKFLOW: SurfaceWorkflowRecordWithInputs = {
  id: CURRENT_RERUN_WORKFLOW_ID,
  name: "Rerun Input Workflow",
  commit_sha: "abcdef1234567890",
  input_schema: {
    query: {
      type: "string",
      required: true,
      default: null,
      description: "Search term",
      sensitive: false,
    },
  },
};

export const EMPTY_RERUN_WORKFLOW: SurfaceWorkflowRecordWithInputs = {
  id: CURRENT_RERUN_WORKFLOW_ID,
  name: "Rerun Input Workflow",
  commit_sha: "abcdef1234567890",
  input_schema: null,
};

export function buildRerunRun(
  overrides: Partial<RunResponse> & {
    workflow_inputs?: Record<string, SurfaceWorkflowInputSnapshotEntry> | null;
  } = {},
): RunResponse {
  return {
    id: "run_rerun_source",
    workflow_id: CURRENT_RERUN_WORKFLOW_ID,
    workflow_name: "Rerun Input Workflow",
    status: "completed",
    started_at: 1_776_120_000,
    completed_at: 1_776_120_030,
    duration_seconds: 30,
    total_cost_usd: 0.01,
    total_tokens: 42,
    created_at: 1_776_119_999,
    branch: "main",
    source: "manual",
    commit_sha: "abcdef1234567890",
    run_number: 12,
    eval_pass_pct: 95,
    eval_score_avg: 0.95,
    regression_count: 0,
    warnings: [],
    workflow_inputs: null,
    workflow_input_schema: null,
    ...overrides,
  } as RunResponse;
}

export function createDeferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;

  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });

  return { promise, resolve, reject };
}
