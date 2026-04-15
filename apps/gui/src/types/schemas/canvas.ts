import type { Node, Edge } from "@xyflow/react";

/** All known block types from Runsight core (spec §2.5), plus any custom string */
export type StepType =
  | "linear"
  | "dispatch"
  | "gate"
  | "synthesize"
  | "workflow"
  | "loop"
  | "team_lead"
  | "engineering_manager"
  | "file_writer"
  | "code"
  | "http_request"
  | (string & {});

export type RunStatus = "idle" | "running" | "completed" | "failed" | "paused" | "pending";

export interface ConditionDef {
  eval_key: string;
  operator: string;
  value?: string | number | boolean | null;
}

export interface ConditionGroupDef {
  combinator?: "and" | "or";
  conditions: ConditionDef[];
}

export interface CaseDef {
  case_id: string;
  condition_group?: ConditionGroupDef;
  default?: boolean;
}

export interface InputRef {
  from: string;
}

/** Node data for canvas steps — maps to BlockDef in RunsightWorkflowFile */
export interface StepNodeData extends Record<string, unknown> {
  /** Identity — maps to block_id (key in blocks dict) */
  stepId: string;
  /** Display label */
  name: string;

  /** Block type (BlockDef.type) */
  stepType: StepType;

  /** Soul references — varies by block type */
  soulRef?: string;      // linear, synthesize, gate, team_lead, engineering_manager
  soulRefs?: string[];   // dispatch

  /** Block-specific fields */
  workflowRef?: string;         // workflow (nested)
  evalKey?: string;             // gate
  extractField?: string;        // gate
  innerBlockRefs?: string[];    // loop
  maxRounds?: number;           // loop
  breakCondition?: Record<string, unknown> | string;  // loop
  carryContext?: Record<string, unknown>;   // loop
  inputBlockIds?: string[];     // synthesize
  outputPath?: string;         // file_writer
  contentKey?: string;          // file_writer
  failureContextKeys?: string[]; // team_lead
  retryConfig?: Record<string, unknown>;  // universal
  stateful?: boolean;                     // universal

  // CodeBlock fields
  code?: string;
  timeoutSeconds?: number;
  allowedImports?: string[];

  // HTTP Request fields
  url?: string;
  method?: string;
  headers?: Record<string, string>;
  body?: string;
  bodyType?: string;
  authType?: string;
  authConfig?: Record<string, string>;
  retryCount?: number;
  retryBackoff?: number | string;
  expectedStatusCodes?: number[];
  allowPrivateIps?: boolean;

  // Universal fields (from BaseBlockDef)
  outputConditions?: CaseDef[];
  inputs?: Record<string, InputRef>;
  outputs?: Record<string, string>;

  // WorkflowBlock additional
  workflowInputs?: Record<string, string>;
  workflowOutputs?: Record<string, string>;
  maxDepth?: number;

  /** Runtime state (not persisted to YAML) */
  status: RunStatus;
  cost?: number;
  executionCost?: number;
  duration?: number;
  tokens?: { input?: number; output?: number; total?: number };
  error?: string | null;
}

export type WorkflowNode = Node<StepNodeData>;
export type WorkflowEdge = Edge;

export type PromptFile = {
  name: string;
  content: string;
};

export type SoulDefinition = {
  id: string;
  name: string;
  model: string;
  description?: string;
  systemPrompt?: string;
  tools?: string[];
  temperature?: number;
  maxTokens?: number;
};

export type WorkflowMeta = {
  id: string;
  name: string;
  projectName: string;
  canvasMode: "dag" | "state-machine";
  lastSavedAt?: string;
  isDirty: boolean;
};

export type LeftSidebarTab = "souls" | "tools";
export type RightPanelTab = "properties" | "prompt" | "yaml";
export type CanvasMode = "dag" | "state-machine";

// ─── RunsightWorkflowFile (YAML schema) ───────────────────────────────────────

export interface SoulDef {
  id: string;
  role: string;
  system_prompt: string;
  tools?: Array<Record<string, unknown>>;
  model_name?: string;
}

export interface BlockDef {
  type: StepType;
  soul_ref?: string;
  soul_refs?: string[];
  input_block_ids?: string[];
  inner_block_refs?: string[];
  max_rounds?: number;
  break_condition?: Record<string, unknown> | string;
  carry_context?: Record<string, unknown>;
  retry_config?: Record<string, unknown>;
  workflow_ref?: string;
  inputs?: Record<string, InputRef> | Record<string, string>;  // InputRef for most blocks, string for WorkflowBlock
  outputs?: Record<string, string>;
  max_depth?: number;
  eval_key?: string;
  extract_field?: string;
  output_path?: string;
  content_key?: string;
  failure_context_keys?: string[];
  code?: string;
  timeout_seconds?: number;
  allowed_imports?: string[];
  // HTTP Request fields (snake_case)
  url?: string;
  method?: string;
  headers?: Record<string, string>;
  body?: string;
  body_type?: string;
  auth_type?: string;
  auth_config?: Record<string, string>;
  retry_count?: number;
  retry_backoff?: number | string;
  expected_status_codes?: number[];
  allow_private_ips?: boolean;
  output_conditions?: CaseDef[];
  stateful?: boolean;
  /** Allow arbitrary fields for unknown block types */
  [key: string]: unknown;
}

export interface TransitionDef {
  from: string;
  to: string | null;
}

export interface ConditionalTransitionDef {
  from: string;
  default?: string | null;
  [decisionKey: string]: string | undefined | null;
}

export interface WorkflowDef {
  name: string;
  entry: string;
  transitions: TransitionDef[];
  conditional_transitions?: ConditionalTransitionDef[];
}

export interface RunsightWorkflowFile {
  version: string;
  config?: Record<string, unknown>;
  blocks: Record<string, BlockDef>;
  workflow: WorkflowDef;
}
