import type { Node, Edge } from "@xyflow/react";

/** All 14 block types from Runsight core (spec §2.5) */
export type StepType =
  | "linear"
  | "fanout"
  | "debate"
  | "message_bus"
  | "router"
  | "gate"
  | "synthesize"
  | "workflow"
  | "retry"
  | "team_lead"
  | "engineering_manager"
  | "placeholder"
  | "file_writer"
  | "code";

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
  soulRef?: string;      // linear, synthesize, router, gate, team_lead, engineering_manager
  soulRefs?: string[];   // fanout, message_bus
  soulARef?: string;     // debate
  soulBRef?: string;     // debate

  /** Block-specific fields */
  iterations?: number;          // debate, message_bus
  workflowRef?: string;         // workflow (nested)
  evalKey?: string;             // gate
  extractField?: string;        // gate
  innerBlockRef?: string;       // retry
  maxRetries?: number;          // retry
  inputBlockIds?: string[];     // synthesize
  outputPath?: string;         // file_writer
  contentKey?: string;          // file_writer
  failureContextKeys?: string[]; // team_lead
  provideErrorContext?: boolean;  // retry

  // CodeBlock fields
  code?: string;
  timeoutSeconds?: number;
  allowedImports?: string[];

  // Universal fields (from BaseBlockDef)
  outputConditions?: CaseDef[];
  inputs?: Record<string, InputRef>;
  outputs?: Record<string, string>;

  // PlaceholderBlock
  description?: string;

  // WorkflowBlock additional
  workflowInputs?: Record<string, string>;
  workflowOutputs?: Record<string, string>;
  maxDepth?: number;

  /** Runtime state (not persisted to YAML) */
  status: RunStatus;
  cost?: number;
  executionCost?: number;
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

export type LeftSidebarTab = "souls" | "tasks" | "tools";
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
  soul_a_ref?: string;
  soul_b_ref?: string;
  input_block_ids?: string[];
  inner_block_ref?: string;
  iterations?: number;
  max_retries?: number;
  workflow_ref?: string;
  inputs?: Record<string, InputRef>;
  outputs?: Record<string, string>;
  max_depth?: number;
  eval_key?: string;
  extract_field?: string;
  output_path?: string;
  content_key?: string;
  provide_error_context?: boolean;
  condition_ref?: string;
  failure_context_keys?: string[];
  code?: string;
  timeout_seconds?: number;
  allowed_imports?: string[];
  output_conditions?: CaseDef[];
  description?: string;
  workflow_inputs?: Record<string, string>;
  workflow_outputs?: Record<string, string>;
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
  souls?: Record<string, SoulDef>;
  blocks: Record<string, BlockDef>;
  workflow: WorkflowDef;
}
