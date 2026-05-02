import { vi } from "vitest";
import type { ContextAuditEventV1 } from "@runsight/shared/zod";

type EventSourceListener = (event: MessageEvent) => void;

export type SurfaceRunStatus = "completed" | "failed" | "running" | "pending";

export type SurfaceRunRecord = {
  id: string;
  workflow_id: string;
  workflow_name: string;
  status: SurfaceRunStatus;
  commit_sha: string;
  duration_seconds: number;
  total_tokens: number;
  total_cost_usd: number;
  source: string;
  branch: string;
  error: string | null;
  created_at: number;
  started_at: number;
  run_number: number | null;
  eval_pass_pct: number | null;
  regression_count: number | null;
  warnings?: Array<Record<string, unknown>>;
};

export type SurfaceWorkflowRecord = {
  id: string;
  name: string;
  yaml: string;
  canvas_state?: {
    nodes?: Array<Record<string, unknown>>;
    edges?: Array<Record<string, unknown>>;
    viewport?: { x: number; y: number; zoom: number };
    selected_node_id?: string | null;
    canvas_mode?: "dag" | "state-machine";
  } | null;
  commit_sha: string;
};

export type SurfaceRunNodeRecord = {
  node_id: string;
  status: string;
  cost_usd?: number;
  duration_seconds?: number;
  tokens?: { input?: number; output?: number; total?: number };
  error?: string | null;
};

export type SurfaceLogEntry = {
  id?: number;
  timestamp: string | number;
  level: string;
  message: string;
};

export const eventSourceInstances: MockEventSource[] = [];

export class MockEventSource {
  static instances = eventSourceInstances;

  public readonly url: string;
  public closed = false;
  public readonly close = vi.fn(() => {
    this.closed = true;
  });
  private readonly listeners = new Map<string, EventSourceListener[]>();

  constructor(url: string) {
    this.url = url;
    eventSourceInstances.push(this);
  }

  addEventListener(type: string, listener: EventSourceListener) {
    const current = this.listeners.get(type) ?? [];
    current.push(listener);
    this.listeners.set(type, current);
  }

  emit(type: string, payload: Record<string, unknown>) {
    if (this.closed) {
      return;
    }

    for (const listener of this.listeners.get(type) ?? []) {
      listener(new MessageEvent(type, { data: JSON.stringify(payload) }));
    }
  }
}

export function buildSurfaceRun(overrides: Partial<SurfaceRunRecord> = {}): SurfaceRunRecord {
  const id = overrides.id ?? "run_readonly_surface";
  const workflowId = overrides.workflow_id ?? "wf_readonly_surface";

  return {
    id,
    workflow_id: workflowId,
    workflow_name: "Readonly Surface Flow",
    status: "completed",
    commit_sha: `${id}_sha`,
    duration_seconds: 88,
    total_tokens: 2112,
    total_cost_usd: 3.14,
    source: "manual",
    branch: "main",
    error: null,
    created_at: 100,
    started_at: 200,
    run_number: null,
    eval_pass_pct: null,
    regression_count: 0,
    warnings: [],
    ...overrides,
  };
}

export function buildBottomPanelRun(
  id: string,
  {
    createdAt,
    runNumber,
    workflowId = "wf_bottom_panel",
  }: {
    createdAt: number;
    runNumber: number;
    workflowId?: string;
  },
): SurfaceRunRecord {
  return buildSurfaceRun({
    id,
    workflow_id: workflowId,
    workflow_name: "Bottom Panel Workflow",
    commit_sha: `${id}_sha`,
    duration_seconds: 30,
    total_tokens: 100,
    total_cost_usd: 0.42,
    created_at: createdAt,
    started_at: createdAt,
    run_number: runNumber,
  });
}

export function buildSurfaceWorkflow(
  overrides: Partial<SurfaceWorkflowRecord> = {},
): SurfaceWorkflowRecord {
  return {
    id: "wf_readonly_surface",
    name: "Readonly Surface Flow",
    yaml: "workflow:\n  name: Live Workflow\n  enabled: true\n",
    canvas_state: {
      nodes: [
        {
          id: "node_brain",
          type: "soul",
          position: { x: 120, y: 80 },
          data: {
            name: "Research Soul",
            soulRef: "souls/researcher",
            model: "gpt-5",
            status: "idle",
            executionCost: 0,
            duration: 0,
          },
        },
      ],
      edges: [],
      viewport: { x: 0, y: 0, zoom: 1 },
      selected_node_id: null,
      canvas_mode: "dag",
    },
    commit_sha: "workflow_commit_readonly",
    ...overrides,
  };
}

export function buildSurfaceRunNode(
  overrides: Partial<SurfaceRunNodeRecord> = {},
): SurfaceRunNodeRecord {
  return {
    node_id: "node_brain",
    status: "completed",
    cost_usd: 1.25,
    duration_seconds: 42,
    tokens: { input: 12, output: 32, total: 44 },
    error: null,
    ...overrides,
  };
}

export function buildSurfaceLogEntry(
  overrides: Partial<SurfaceLogEntry> = {},
): SurfaceLogEntry {
  return {
    timestamp: "2026-04-22T13:00:00.000Z",
    level: "info",
    message: "Node draft started",
    ...overrides,
  };
}

export function buildSurfaceReplayEvent(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    event: "block_start",
    block_id: "draft",
    ...overrides,
  };
}

export function buildContextAuditEvent(
  overrides: Partial<ContextAuditEventV1> = {},
): ContextAuditEventV1 {
  const runId = overrides.run_id ?? "run_readonly_surface";
  const nodeId = overrides.node_id ?? "node_brain";
  const sequence = overrides.sequence ?? 1;

  return {
    schema_version: "context_audit.v1",
    event: "context_resolution",
    run_id: runId,
    workflow_name: "Readonly Surface Flow",
    node_id: nodeId,
    block_type: "linear",
    access: "declared",
    mode: "strict",
    sequence,
    records: [
      {
        input_name: "brief",
        from_ref: "research.summary",
        namespace: "results",
        source: "research",
        field_path: "summary",
        status: "resolved",
        severity: "allow",
        value_type: "str",
        preview: "context from the selected audit run",
        reason: null,
        internal: false,
      },
    ],
    resolved_count: 1,
    denied_count: 0,
    warning_count: 0,
    emitted_at: `2026-04-17T10:0${sequence}:00.000Z`,
    ...overrides,
  };
}

export function buildBottomPanelContextResolutionEvent(
  runId: string,
  nodeId: string,
  sequence: number,
): ContextAuditEventV1 {
  return buildContextAuditEvent({
    run_id: runId,
    workflow_name: "Bottom Panel Workflow",
    node_id: nodeId,
    sequence,
    records: [
      {
        input_name: "context",
        from_ref: "draft.summary",
        namespace: "results",
        source: "draft",
        field_path: "summary",
        status: "resolved",
        severity: "allow",
        value_type: "str",
        preview: "summary",
        reason: null,
        internal: false,
      },
    ],
    resolved_count: 0,
    emitted_at: `2026-04-22T13:0${sequence}:00.000Z`,
  });
}
